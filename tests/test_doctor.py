import contextlib
import io
import json
import os
import pathlib
import plistlib
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock

from _loader import load_macpulse  # noqa: F401

import macpulse_doctor as doc


class HomeCase(unittest.TestCase):
    def setUp(self):
        self.home = pathlib.Path(tempfile.mkdtemp(prefix="macpulse-doctor-"))
        patcher = mock.patch.dict(os.environ, {"HOME": str(self.home)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def status(self, name, version="1.4.0"):
        return {c["name"]: c for c in doc.collect(version)}[name]


class DoctorRun(HomeCase):
    def test_json_shape_and_exit_code(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = doc.run(as_json=True, version="1.4.0")
        data = json.loads(buf.getvalue())
        self.assertIsInstance(rc, int)
        self.assertEqual(data["version"], "1.4.0")
        self.assertEqual({c["name"] for c in data["checks"]},
                         {"cli_version", "app_bundle_version", "launch_agent",
                          "history_db", "repo_sync", "brief_hook"})
        for c in data["checks"]:
            self.assertEqual(set(c), {"name", "status", "detail"})
            self.assertIn(c["status"], ("OK", "WARN", "FAIL"))
        has_fail = any(c["status"] == "FAIL" for c in data["checks"])
        self.assertEqual(rc, 1 if has_fail else 0)

    def test_text_mode_one_line_per_check(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            doc.run(as_json=False, version="1.4.0")
        lines = [l for l in buf.getvalue().splitlines() if l.strip()]
        self.assertGreaterEqual(len(lines), 7)            # six checks + summary
        self.assertTrue(lines[0].startswith(("OK", "WARN", "FAIL")))

    def test_crashing_check_never_crashes_doctor(self):
        def boom(version):
            raise ValueError("kaput")
        n = len(doc.CHECKS)
        with mock.patch.object(doc, "CHECKS", (("boom", boom),) + doc.CHECKS):
            res = doc.collect("1.4.0")
        self.assertEqual(res[0]["status"], "FAIL")
        self.assertEqual(len(res), n + 1)


class DoctorChecks(HomeCase):
    def test_app_bundle_missing_is_warn(self):
        self.assertEqual(self.status("app_bundle_version")["status"], "WARN")

    def _plist(self, version):
        d = self.home / "Applications" / "macpulse.app" / "Contents"
        d.mkdir(parents=True, exist_ok=True)
        (d / "Info.plist").write_bytes(plistlib.dumps({"CFBundleShortVersionString": version}))
        exe = d / "MacOS" / "macpulse"
        exe.parent.mkdir(exist_ok=True)
        exe.write_bytes(b"\xcf\xfa\xed\xfe" + b"\0" * 60)    # 64-bit Mach-O magic
        exe.chmod(0o755)

    def test_app_bundle_with_broken_executable_is_fail(self):
        self._plist("1.4.0")
        exe = self.home / "Applications" / "macpulse.app" / "Contents" / "MacOS" / "macpulse"
        exe.write_text("stale")
        self.assertEqual(self.status("app_bundle_version")["status"], "FAIL")
        exe.unlink()
        self.assertEqual(self.status("app_bundle_version")["status"], "FAIL")

    def test_app_bundle_match_and_mismatch(self):
        self._plist("1.4.0")
        self.assertEqual(self.status("app_bundle_version")["status"], "OK")
        self._plist("1.3.0")
        self.assertEqual(self.status("app_bundle_version")["status"], "WARN")

    def _launchctl(self, returncode, stdout):
        cp = subprocess.CompletedProcess([], returncode, stdout, "")
        return mock.patch.object(doc.subprocess, "run", return_value=cp)

    def test_launch_agent_states(self):
        with self._launchctl(113, ""):
            self.assertEqual(self.status("launch_agent")["status"], "FAIL")
        with self._launchctl(0, "state = running\n"):
            self.assertEqual(self.status("launch_agent")["status"], "WARN")
        with self._launchctl(0, "\tpid = %d\n" % os.getpid()):
            c = self.status("launch_agent")
            self.assertEqual(c["status"], "OK")
            self.assertIn(str(os.getpid()), c["detail"])
        with self._launchctl(0, "\tpid = 999999999\n"):
            self.assertEqual(self.status("launch_agent")["status"], "WARN")

    def test_history_db(self):
        self.assertEqual(self.status("history_db")["status"], "WARN")
        d = self.home / "Library" / "Application Support" / "macpulse"
        d.mkdir(parents=True)
        con = sqlite3.connect(d / "history.db")
        con.execute("create table t(x)")
        con.commit()
        con.close()
        self.assertEqual(self.status("history_db")["status"], "OK")

    def test_history_db_corrupt_is_not_ok(self):
        d = self.home / "Library" / "Application Support" / "macpulse"
        d.mkdir(parents=True)
        (d / "history.db").write_bytes(b"this is definitely not sqlite" * 50)
        self.assertIn(self.status("history_db")["status"], ("FAIL", "WARN"))

    def test_repo_sync(self):
        self.assertEqual(self.status("repo_sync")["detail"], "no repo")
        b = self.home / ".local" / "bin"
        (b / "macpulse-dist").mkdir(parents=True)
        (b / "macpulse").write_text("a")
        (b / "macpulse-dist" / "macpulse").write_text("a")
        self.assertEqual(self.status("repo_sync")["status"], "OK")
        (b / "macpulse-dist" / "macpulse").write_text("b")
        c = self.status("repo_sync")
        self.assertEqual(c["status"], "WARN")
        self.assertIn("macpulse", c["detail"])

    def test_brief_hook(self):
        self.assertEqual(self.status("brief_hook")["status"], "WARN")
        s = self.home / ".claude"
        s.mkdir()
        hook = {"type": "command", "command": '"$HOME/.local/bin/macpulse" --brief || true'}
        (s / "settings.json").write_text(json.dumps(
            {"hooks": {"SessionStart": [{"matcher": "startup", "hooks": [hook]}]}}))
        self.assertEqual(self.status("brief_hook")["status"], "OK")

    def test_brief_hook_text_elsewhere_does_not_count(self):
        # Refuter case: the phrase in a Stop hook or a note is not a SessionStart hook.
        s = self.home / ".claude"
        s.mkdir()
        stop = {"type": "command", "command": "echo disabled macpulse --brief"}
        (s / "settings.json").write_text(json.dumps(
            {"note": "macpulse --brief removed",
             "hooks": {"Stop": [{"hooks": [stop]}]}}))
        self.assertEqual(self.status("brief_hook")["status"], "WARN")


if __name__ == "__main__":
    unittest.main()
