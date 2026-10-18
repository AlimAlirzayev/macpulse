"""release.sh output, the verified install path, and the menu bar --print-title mode."""
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from _loader import ROOT

SHIPPED = ["macpulse", "macpulse_doctor.py", "macpulse_history.py", "macpulse_mcp.py",
           "macpulse_strings.py", "menubar.m", "install.sh", "LICENSE", "README.md"]


def stage_tree():
    """A throwaway copy of the repo's shipped files plus release.sh."""
    d = Path(tempfile.mkdtemp(prefix="macpulse-rel-"))
    for f in SHIPPED + ["release.sh"]:
        shutil.copy2(ROOT / f, d / f)
    return d


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ReleaseScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = stage_tree()
        cls.proc = subprocess.run(["bash", "release.sh"], cwd=cls.tree, capture_output=True,
                                 text=True, timeout=30)

    def test_exits_zero(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)

    def test_sha256sums_lists_every_shipped_file_correctly(self):
        lines = (self.tree / "SHA256SUMS").read_text().splitlines()
        listed = {l.split(None, 1)[1].lstrip("*"): l.split()[0] for l in lines}
        self.assertEqual(set(listed), set(SHIPPED))
        for name, digest in listed.items():
            self.assertEqual(digest, sha(self.tree / name), name)

    def test_sha256sums_passes_shasum_check(self):
        r = subprocess.run(["shasum", "-a", "256", "-c", "SHA256SUMS"], cwd=self.tree,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_sbom_is_cyclonedx_15(self):
        bom = json.loads((self.tree / "sbom.cdx.json").read_text())
        self.assertEqual(bom["bomFormat"], "CycloneDX")
        self.assertEqual(bom["specVersion"], "1.5")
        self.assertRegex(bom["serialNumber"], r"^urn:uuid:[0-9a-f-]{36}$")
        self.assertEqual(bom["metadata"]["component"]["name"], "macpulse")

    def test_sbom_version_comes_from_cli_source(self):
        src = (self.tree / "macpulse").read_text()
        version = next(l for l in src.splitlines() if l.startswith('VERSION = "')).split('"')[1]
        bom = json.loads((self.tree / "sbom.cdx.json").read_text())
        self.assertEqual(bom["metadata"]["component"]["version"], version)

    def test_sbom_components_match_files_and_hashes(self):
        bom = json.loads((self.tree / "sbom.cdx.json").read_text())
        comps = {c["name"]: c for c in bom["components"]}
        self.assertEqual(set(comps), set(SHIPPED))
        for name, c in comps.items():
            self.assertEqual(c["type"], "file")
            self.assertEqual(c["hashes"], [{"alg": "SHA-256", "content": sha(self.tree / name)}])
        self.assertNotIn("dependencies", bom)

    def test_sbom_is_gitignored_but_sums_are_not(self):
        ignore = (ROOT / ".gitignore").read_text().split()
        self.assertIn("sbom.cdx.json", ignore)
        self.assertNotIn("SHA256SUMS", ignore)


class VerifiedInstall(unittest.TestCase):
    """install.sh piped on stdin takes the download branch; HOME is a sandbox."""

    @classmethod
    def setUpClass(cls):
        cls.stubs = Path(tempfile.mkdtemp(prefix="macpulse-stubs-"))
        for name in ("clang", "launchctl"):          # no compiler, no launchd side effects
            p = cls.stubs / name
            p.write_text("#!/bin/bash\nexit 1\n")
            p.chmod(p.stat().st_mode | stat.S_IEXEC)

    def install(self, base_dir):
        home = Path(tempfile.mkdtemp(prefix="macpulse-home-"))
        env = dict(os.environ, HOME=str(home), PATH=f"{self.stubs}:{os.environ['PATH']}",
                   MACPULSE_BASE=f"file://{base_dir}")
        env.pop("MACPULSE_TEST_HOME", None)
        with open(ROOT / "install.sh", "rb") as script:
            r = subprocess.run(["bash"], stdin=script, env=env, capture_output=True,
                               text=True, timeout=60)
        return r, home

    def release_tree(self):
        tree = stage_tree()
        subprocess.run(["bash", "release.sh"], cwd=tree, check=True, capture_output=True)
        return tree

    def test_install_script_syntax(self):
        self.assertEqual(subprocess.run(["bash", "-n", str(ROOT / "install.sh")]).returncode, 0)

    def test_intact_download_installs(self):
        r, home = self.install(self.release_tree())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((home / ".local/bin/macpulse").exists())
        self.assertTrue((home / ".local/bin/macpulse_mcp.py").exists())
        self.assertIn("checksums verified", r.stdout)

    def test_one_tampered_byte_installs_nothing(self):
        tree = self.release_tree()
        with open(tree / "macpulse_strings.py", "ab") as fh:
            fh.write(b"#")
        r, home = self.install(tree)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("mismatch", r.stdout + r.stderr)
        self.assertFalse((home / ".local").exists(), list(home.rglob("*")))
        self.assertFalse((home / "Applications").exists())

    def test_missing_sha256sums_installs_nothing(self):
        tree = self.release_tree()
        (tree / "SHA256SUMS").unlink()
        r, home = self.install(tree)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((home / ".local").exists())

    def test_file_missing_from_sums_installs_nothing(self):
        tree = self.release_tree()
        lines = [l for l in (tree / "SHA256SUMS").read_text().splitlines()
                 if not l.endswith("macpulse_doctor.py")]
        (tree / "SHA256SUMS").write_text("\n".join(lines) + "\n")
        r, home = self.install(tree)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((home / ".local").exists())

    def test_bundle_version_matches_cli(self):
        text = (ROOT / "install.sh").read_text()
        src = (ROOT / "macpulse").read_text()
        version = next(l for l in src.splitlines() if l.startswith('VERSION = "')).split('"')[1]
        self.assertIn(f"<key>CFBundleShortVersionString</key><string>{version}</string>", text)
        self.assertIn(f"<key>CFBundleVersion</key><string>{version}</string>", text)


@unittest.skipUnless(shutil.which("clang"), "clang not available")
class MenubarPrintTitle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="macpulse-mb-"))
        cls.bin = cls.tmp / "mb"
        r = subprocess.run(["clang", "-fobjc-arc", "-O2", "-mmacosx-version-min=12.0",
                            "-framework", "AppKit", str(ROOT / "menubar.m"), "-o", str(cls.bin)],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise unittest.SkipTest("menubar.m did not compile: " + r.stderr[-500:])

    def title(self, payload, raw=False):
        stub = self.tmp / "stub"
        body = payload if raw else json.dumps(payload)
        stub.write_text("#!/bin/bash\ncat <<'EOF'\n" + body + "\nEOF\n")
        stub.chmod(0o755)
        env = dict(os.environ, MACPULSE_BIN=str(stub))
        return subprocess.run([str(self.bin), "--print-title"], env=env, capture_output=True,
                              text=True, timeout=20)

    def test_complete_scan_has_no_question_mark(self):
        r = self.title({"score": 100, "complete": True, "checks": {"run": 9, "failed": []}})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "◍ 100")

    def test_incomplete_scan_is_marked(self):
        r = self.title({"score": 100, "complete": False,
                        "checks": {"run": 9, "failed": ["battery"]}})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "◍ 100?")

    def test_legacy_payload_without_complete_is_complete(self):
        self.assertEqual(self.title({"score": 42}).stdout.strip(), "◍ 42")

    def test_unreadable_output_is_flagged_not_fabricated(self):
        r = self.title("not json", raw=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("?", r.stdout)

    def test_env_override_selects_the_binary(self):
        a = self.title({"score": 71, "complete": True}).stdout.strip()
        b = self.title({"score": 88, "complete": True}).stdout.strip()
        self.assertEqual((a, b), ("◍ 71", "◍ 88"))


if __name__ == "__main__":
    unittest.main()
