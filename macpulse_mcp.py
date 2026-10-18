"""macpulse --mcp: a minimal read-only MCP server over stdio.

Transport: newline-delimited JSON-RPC 2.0 (one JSON object per line). Exposes two
read-only tools, `scan` and `explain_score`. There is deliberately no tool that
fixes, kills, quits or deletes anything. Stdout carries protocol messages only;
anything the scan prints is redirected to stderr.
"""
import contextlib
import json
import sys

DEFAULT_PROTOCOL = "2025-06-18"
LANG_SCHEMA = {
    "type": "object",
    "properties": {"lang": {"type": "string", "enum": ["az", "en", "ru"], "default": "en",
                            "description": "Language of finding titles and details."}},
    "additionalProperties": False,
}
TOOLS = [
    {"name": "scan",
     "description": "Run a full read-only macpulse health scan: score, grade, verdicts "
                    "and ranked findings. Changes nothing on the machine.",
     "inputSchema": LANG_SCHEMA, "annotations": {"readOnlyHint": True}},
    {"name": "explain_score",
     "description": "Explain the health score: the score plus the per-deduction "
                    "breakdown (key, reason, points). Read-only.",
     "inputSchema": LANG_SCHEMA, "annotations": {"readOnlyHint": True}},
]
TOOL_NAMES = {t["name"] for t in TOOLS}


def _ok(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def _call_tool(scan_fn, params):
    name = params.get("name")
    args = params.get("arguments") or {}
    lang = args.get("lang", "en") if isinstance(args, dict) else "en"
    if lang not in ("az", "en", "ru"):
        lang = "en"
    with contextlib.redirect_stdout(sys.stderr):
        payload = scan_fn(lang)
    if name == "explain_score":
        payload = {"score": payload.get("score"), "grade": payload.get("grade"),
                   "score_breakdown": payload.get("score_breakdown", [])}
    return {"content": [{"type": "text", "text": json.dumps(payload, default=str)}],
            "isError": False}


def handle(scan_fn, version, msg):
    """Return the response dict for one parsed message, or None for notifications."""
    if not isinstance(msg, dict) or "method" not in msg:
        return _err(msg.get("id") if isinstance(msg, dict) else None, -32600,
                    "Invalid Request")
    method, rid = msg["method"], msg.get("id")
    is_note = "id" not in msg
    params = msg.get("params") or {}
    if not isinstance(method, str):
        return _err(rid, -32600, "Invalid Request")
    if method == "initialize":
        proto = params.get("protocolVersion") if isinstance(params, dict) else None
        return _ok(rid, {"protocolVersion": proto or DEFAULT_PROTOCOL,
                         "capabilities": {"tools": {}},
                         "serverInfo": {"name": "macpulse", "version": version}})
    if method == "ping":
        return None if is_note else _ok(rid, {})
    if method == "tools/list":
        return _ok(rid, {"tools": TOOLS})
    if method == "tools/call":
        if not isinstance(params, dict):
            return _err(rid, -32602, "Invalid params")
        name = params.get("name")
        # A list or dict name is unhashable; checking the type first keeps a malformed
        # call a -32602 answer instead of a crash that silences every later request.
        if not isinstance(name, str) or name not in TOOL_NAMES:
            return _err(rid, -32602, f"Unknown tool: {name!r}")
        if not isinstance(params.get("arguments", {}) or {}, dict):
            return _err(rid, -32602, "arguments must be an object")
        try:
            return _ok(rid, _call_tool(scan_fn, params))
        except Exception as e:
            return _ok(rid, {"content": [{"type": "text", "text": f"scan failed: {e}"}],
                             "isError": True})
    if is_note:
        return None                      # notifications/initialized and friends
    return _err(rid, -32601, f"Method not found: {method}")


def serve(scan_fn, version):
    out = sys.stdout                      # captured once; scans are redirected away from it
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            resp = _err(None, -32700, "Parse error")
        else:
            try:
                resp = handle(scan_fn, version, msg)
            except Exception as e:          # last line of defence: answer, keep serving
                rid = msg.get("id") if isinstance(msg, dict) else None
                resp = _err(rid, -32603, f"Internal error: {type(e).__name__}")
        if resp is not None:
            out.write(json.dumps(resp) + "\n")
            out.flush()
    return 0
