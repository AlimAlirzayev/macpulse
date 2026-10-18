"""Shared test bootstrap: isolate HOME, then load the product from the repo.

HOME is pointed at a throwaway directory BEFORE macpulse is imported, so the history
database and every other path under ~ can never touch the real one.
"""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if "MACPULSE_TEST_HOME" not in os.environ:
    os.environ["MACPULSE_TEST_HOME"] = tempfile.mkdtemp(prefix="macpulse-test-home-")
    os.environ["HOME"] = os.environ["MACPULSE_TEST_HOME"]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_macpulse():
    if "macpulse" in sys.modules:
        return sys.modules["macpulse"]
    loader = importlib.machinery.SourceFileLoader("macpulse", str(ROOT / "macpulse"))
    spec = importlib.util.spec_from_loader("macpulse", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["macpulse"] = mod
    loader.exec_module(mod)
    return mod
