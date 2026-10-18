import contextlib
import io
import json
import sys
import unittest

from _loader import load_macpulse  # noqa: F401

import macpulse_mcp


def fake_scan(lang):
    print("noise a real scan might print")        # must never reach the protocol stream
    return {"score": 73, "grade": "attention", "lang": lang, "findings": [],
            "score_breakdown": [{"key": "swap", "reason": "swap", "points": 27}]}


def drive(lines, scan_fn=fake_scan):
    stdin = io.StringIO("".join(l if l.endswith("\n") else l + "\n" for l in lines))
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stderr(stderr):
        old = sys.stdin, sys.stdout
        sys.stdin, sys.stdout = stdin, stdout
        try:
            rc = macpulse_mcp.serve(scan_fn, "1.4.0")
        finally:
            sys.stdin, sys.stdout = old
    replies = [json.loads(l) for l in stdout.getvalue().splitlines()]
    return rc, replies, stdout.getvalue()


def rpc(i, method, params=None):
    msg = {"jsonrpc": "2.0", "id": i, "method": method}
    if params is not None:
        msg["params"] = params
    return json.dumps(msg)


class McpServer(unittest.TestCase):
    def test_initialize(self):
        rc, (r,), _ = drive([rpc(1, "initialize", {"protocolVersion": "2024-11-05"})])
        self.assertEqual(rc, 0)
        self.assertEqual(r["id"], 1)
        res = r["result"]
        self.assertEqual(res["serverInfo"], {"name": "macpulse", "version": "1.4.0"})
        self.assertEqual(res["protocolVersion"], "2024-11-05")
        self.assertIn("tools", res["capabilities"])

    def test_initialize_default_protocol(self):
        _, (r,), _ = drive([rpc(1, "initialize", {})])
        self.assertEqual(r["result"]["protocolVersion"], "2025-06-18")

    def test_initialized_notification_gets_no_reply(self):
        _, replies, _ = drive([json.dumps({"jsonrpc": "2.0",
                                           "method": "notifications/initialized"})])
        self.assertEqual(replies, [])

    def test_ping(self):
        _, (r,), _ = drive([rpc(7, "ping")])
        self.assertEqual(r["result"], {})

    def test_tools_list_names_and_read_only(self):
        _, (r,), _ = drive([rpc(2, "tools/list")])
        tools = r["result"]["tools"]
        self.assertEqual({t["name"] for t in tools}, {"scan", "explain_score"})
        for t in tools:
            self.assertEqual(t["inputSchema"]["type"], "object")
            self.assertTrue(t["annotations"]["readOnlyHint"])
            self.assertEqual(t["inputSchema"]["properties"]["lang"]["enum"],
                             ["az", "en", "ru"])

    def test_call_scan(self):
        _, (r,), _ = drive([rpc(3, "tools/call", {"name": "scan",
                                                  "arguments": {"lang": "ru"}})])
        res = r["result"]
        self.assertFalse(res["isError"])
        payload = json.loads(res["content"][0]["text"])
        self.assertEqual(payload["score"], 73)
        self.assertEqual(payload["lang"], "ru")

    def test_call_explain_score_is_trimmed(self):
        _, (r,), _ = drive([rpc(4, "tools/call", {"name": "explain_score"})])
        payload = json.loads(r["result"]["content"][0]["text"])
        self.assertEqual(payload["score"], 73)
        self.assertEqual(payload["score_breakdown"][0]["points"], 27)
        self.assertNotIn("findings", payload)

    def test_unknown_method(self):
        _, (r,), _ = drive([rpc(5, "resources/list")])
        self.assertEqual(r["error"]["code"], -32601)
        self.assertEqual(r["id"], 5)

    def test_malformed_line_then_keeps_serving(self):
        rc, replies, _ = drive(["{not json", rpc(6, "ping")])
        self.assertEqual(rc, 0)
        self.assertEqual(replies[0]["error"]["code"], -32700)
        self.assertEqual(replies[1]["id"], 6)

    def test_stdout_is_protocol_only(self):
        _, _, raw = drive([rpc(1, "tools/call", {"name": "scan"})])
        for line in raw.splitlines():
            self.assertEqual(json.loads(line)["jsonrpc"], "2.0")

    def test_scan_failure_is_reported_not_fatal(self):
        def boom(lang):
            raise RuntimeError("ps exploded")
        _, replies, _ = drive([rpc(1, "tools/call", {"name": "scan"}), rpc(2, "ping")],
                              scan_fn=boom)
        self.assertTrue(replies[0]["result"]["isError"])
        self.assertEqual(replies[1]["id"], 2)

    def test_no_mutating_tool_exposed(self):
        names = {t["name"] for t in macpulse_mcp.TOOLS}
        for bad in ("fix", "kill", "quit", "delete"):
            self.assertFalse(any(bad in n for n in names), bad)

    def test_unknown_tool_is_an_error(self):
        _, (r,), _ = drive([rpc(1, "tools/call", {"name": "kill_everything"})])
        self.assertIn("error", r)

    def test_malformed_params_never_kill_the_server(self):
        # Refuter case: an unhashable tool name crashed the loop and silenced the ping.
        lines = [rpc(1, "tools/call", {"name": ["scan"]}),
                 rpc(2, "tools/call", {"name": {"x": 1}}),
                 rpc(3, "tools/call", {"name": "scan", "arguments": ["en"]}),
                 json.dumps({"jsonrpc": "2.0", "id": 4, "method": ["ping"]}),
                 rpc(5, "ping")]
        _, replies, _ = drive(lines)
        self.assertEqual(len(replies), 5)
        for r in replies[:4]:
            self.assertIn("error", r)
        self.assertEqual(replies[4].get("result"), {})


if __name__ == "__main__":
    unittest.main()
