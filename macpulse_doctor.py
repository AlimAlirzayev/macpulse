"""macpulse --doctor: self-diagnosis of the macpulse installation.

Read-only. Each check returns (status, detail) and is wrapped so that one failing
check can never crash the doctor. This module deliberately does not import macpulse
(that would be circular); the CLI passes in the version string.
"""
import json
import os
import pathlib
import plistlib
import re
import sqlite3
import subprocess
import time

LABEL = "io.macpulse.agent"
SYNC_FILES = ("macpulse", "macpulse_history.py", "macpulse_strings.py",
              "macpulse_doctor.py", "macpulse_mcp.py")
OK, WARN, FAIL = "OK", "WARN", "FAIL"


def _home():
    return pathlib.Path(os.environ.get("HOME") or pathlib.Path.home())


def _cli_version(version):
    return OK, version


MACHO_MAGIC = {b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}


def _app_bundle_version(version):
    plist = _home() / "Applications" / "macpulse.app" / "Contents" / "Info.plist"
    if not plist.exists():
        return WARN, "app bundle not installed (~/Applications/macpulse.app)"
    with open(plist, "rb") as fh:
        bundle = plistlib.load(fh).get("CFBundleShortVersionString", "?")
    if bundle != version:
        return WARN, f"app bundle {bundle} != cli {version} (re-run install.sh)"
    # Info.plist alone can describe a bundle whose program is gone or broken.
    exe = plist.parent / "MacOS" / "macpulse"
    try:
        with open(exe, "rb") as fh:
            magic = fh.read(4)
    except OSError:
        return FAIL, "app bundle has no executable (re-run install.sh)"
    if magic not in MACHO_MAGIC or not os.access(exe, os.X_OK):
        return FAIL, "app bundle executable is not a runnable Mach-O binary (re-run install.sh)"
    return OK, f"app bundle {bundle}"


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _launch_agent(version):
    target = f"gui/{os.getuid()}/{LABEL}"
    try:
        r = subprocess.run(["launchctl", "print", target], capture_output=True,
                           text=True, timeout=2)
    except FileNotFoundError:
        return WARN, "launchctl not available on this system"
    if r.returncode != 0:
        return FAIL, f"{LABEL} not loaded"
    m = re.search(r"^\s*pid\s*=\s*(\d+)", r.stdout, re.M)
    if not m:
        return WARN, "loaded, no running pid"
    pid = int(m.group(1))
    if not _pid_alive(pid):
        return WARN, f"loaded, pid {pid} is not alive"
    return OK, f"loaded, pid {pid}"


def _history_db(version):
    db = _home() / "Library" / "Application Support" / "macpulse" / "history.db"
    if not db.exists():
        return WARN, "history.db missing (created on first scan)"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1)
    try:
        row = con.execute("PRAGMA integrity_check").fetchone()
    finally:
        con.close()
    verdict = row[0] if row else "no result"
    if verdict != "ok":
        return FAIL, f"integrity_check: {verdict}"
    return OK, "integrity ok"


def _repo_sync(version):
    bin_dir = _home() / ".local" / "bin"
    repo = bin_dir / "macpulse-dist"
    if not repo.is_dir():
        return OK, "no repo"
    differ = []
    for name in SYNC_FILES:
        local, mirror = bin_dir / name, repo / name
        if not local.exists() and not mirror.exists():
            continue
        if not local.exists() or not mirror.exists():
            differ.append(f"{name} (missing on one side)")
        elif local.read_bytes() != mirror.read_bytes():
            differ.append(name)
    if differ:
        return WARN, "differs from repo: " + ", ".join(differ)
    return OK, "local copies match repo"


def _brief_hook(version):
    settings = _home() / ".claude" / "settings.json"
    if not settings.exists():
        return WARN, "~/.claude/settings.json not found"
    try:
        data = json.loads(settings.read_text(errors="replace"))
    except ValueError:
        return WARN, "~/.claude/settings.json is not valid JSON"
    # Only a SessionStart hook counts. A text search also matched comments, notes and
    # hooks on other events (found by the refuter), so it reported a hook that never runs.
    if isinstance(data, dict) and data.get("disableAllHooks") is True:
        return WARN, "hooks are disabled (disableAllHooks: true)"
    groups = ((data.get("hooks") or {}).get("SessionStart") or []) if isinstance(data, dict) else []
    for group in groups if isinstance(groups, list) else []:
        for hook in (group.get("hooks") or []) if isinstance(group, dict) else []:
            cmd = hook.get("command", "") if isinstance(hook, dict) else ""
            # The flag must be exactly --brief, and not inside a shell comment.
            live = cmd.split("#", 1)[0] if isinstance(cmd, str) else ""
            if re.search(r"macpulse[\\\"']*\s+--brief(?![\w-])", live):
                return OK, "SessionStart hook present"
    return WARN, "no SessionStart hook runs 'macpulse --brief'"


CHECKS = (
    ("cli_version", _cli_version),
    ("app_bundle_version", _app_bundle_version),
    ("launch_agent", _launch_agent),
    ("history_db", _history_db),
    ("repo_sync", _repo_sync),
    ("brief_hook", _brief_hook),
)


def collect(version="?"):
    results = []
    for name, fn in CHECKS:
        try:
            status, detail = fn(version)
        except Exception as e:  # one broken check must never take the doctor down
            status, detail = FAIL, f"check crashed: {type(e).__name__}: {e}"
        results.append({"name": name, "status": status, "detail": detail})
    return results


def run(as_json=False, version="?"):
    t0 = time.time()
    checks = collect(version)
    failed = sum(1 for c in checks if c["status"] == FAIL)
    warned = sum(1 for c in checks if c["status"] == WARN)
    if as_json:
        print(json.dumps({"version": version, "checks": checks}, indent=2))
    else:
        for c in checks:
            print(f"{c['status']:<5} {c['name']:<19} {c['detail']}")
        print(f"\nmacpulse {version} doctor: {len(checks) - failed - warned} ok, "
              f"{warned} warn, {failed} fail ({time.time() - t0:.1f}s)")
    return 1 if failed else 0
