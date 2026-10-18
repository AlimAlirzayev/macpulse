"""Scoring, checks and parsers — pure functions fed fixture dicts, no subprocesses."""
import unittest

from _loader import load_macpulse

mp = load_macpulse()
GB = 1024 ** 3
MEMORY_FAMILY = ("swap", "pressure", "hog:")


def fixture(**over):
    mem = {
        "total": 8 * GB, "wired": 1.5 * GB, "active": 2.5 * GB, "compressed": 2 * GB,
        "swap_used_mb": 200.0, "swap_total_mb": 1024.0, "free_pct": 60,
        "uptime_days": 3, "disk_free": 120 * GB, "disk_total": 245 * 10 ** 9,
        "pressure_level": "normal",
        "thermal": {"speed_limit": 100, "throttled": False},
        "battery": {"present": False, "cycle_count": None, "capacity_pct": None,
                    "condition": None},
    }
    mem.update(over)
    return mem


def incident_mem():
    """2026-09-17: 8 GB Mac, 8.4 GB in swap, 306 MB of disk left."""
    return fixture(swap_used_mb=8601, swap_total_mb=9216, free_pct=30, uptime_days=3,
                   disk_free=306 * 1024 * 1024, disk_total=245 * 10 ** 9,
                   pressure_level="critical")


def finding(sev, key, category=None):
    return mp.Finding(sev, key, category or mp.CAT_MEMORY, key + ".t", key + ".d", {})


def breakdown_total(findings, mem):
    return sum(p["points"] for p in mp.score_breakdown(findings, mem))


class _NoDiskWalk:
    """check_disk walks the real disk when short on space; keep tests hermetic."""

    def setUp(self):
        self._saved = (mp.reclaim_candidates, mp.space_holders)
        mp.reclaim_candidates = lambda *a, **k: []
        mp.space_holders = lambda *a, **k: []

    def tearDown(self):
        mp.reclaim_candidates, mp.space_holders = self._saved


class IncidentReplay(_NoDiskWalk, unittest.TestCase):
    def test_version(self):
        self.assertEqual(mp.VERSION, "1.4.0")

    def test_incident_has_critical_finding(self):
        mem = incident_mem()
        found = mp.check_memory([], mem) + mp.check_disk([], mem)
        self.assertTrue(any(f.sev == "critical" for f in found), [f.key for f in found])

    def test_incident_flags_both_swap_and_disk(self):
        mem = incident_mem()
        keys = {f.key for f in mp.check_memory([], mem) + mp.check_disk([], mem)}
        self.assertIn("swap", keys)
        self.assertIn("disk", keys)

    def test_incident_score_is_struggling(self):
        mem = incident_mem()
        found = mp.check_memory([], mem) + mp.check_disk([], mem)
        s = mp.score(found, mem)
        self.assertLess(s, 65)
        self.assertEqual(mp.grade_key(s), "grade.struggling")


class HealthyFixture(_NoDiskWalk, unittest.TestCase):
    def test_no_memory_or_disk_findings(self):
        mem = fixture()
        self.assertEqual(mp.check_memory([], mem), [])
        self.assertEqual(mp.check_disk([], mem), [])

    def test_score_is_healthy(self):
        mem = fixture()
        self.assertGreaterEqual(mp.score([], mem), 85)
        self.assertEqual(mp.grade_key(mp.score([], mem)), "grade.healthy")

    def test_healthy_has_empty_breakdown(self):
        self.assertEqual(mp.score_breakdown([], fixture()), [])


class ScoreIdentity(unittest.TestCase):
    MIXES = [
        [],
        [("warn", "cpu")],
        [("critical", "swap")],
        [("critical", "swap"), ("warn", "disk"), ("warn", "ghost"), ("info", "uptime")],
        [("critical", "swap"), ("critical", "pressure"), ("critical", "hog:a"),
         ("critical", "hog:b"), ("critical", "disk"), ("critical", "x"), ("critical", "y"),
         ("critical", "z"), ("critical", "w")],
    ]

    def test_score_equals_clamped_100_minus_breakdown(self):
        for free_pct in (0, 12, 60):
            mem = fixture(free_pct=free_pct)
            for mix in self.MIXES:
                found = [finding(s, k) for s, k in mix]
                expected = max(0, min(100, 100 - breakdown_total(found, mem)))
                self.assertEqual(mp.score(found, mem), expected, (mix, free_pct))

    def test_breakdown_shape(self):
        found = [finding("critical", "swap"), finding("warn", "disk")]
        rows = mp.score_breakdown(found, fixture())
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(set(row), {"key", "reason", "points"})
            self.assertIsInstance(row["points"], int)
            self.assertGreater(row["points"], 0)
            self.assertTrue(row["reason"])

    def test_score_is_bounded(self):
        found = [finding("critical", f"k{i}", mp.CAT_CPU if hasattr(mp, "CAT_CPU")
                         else mp.CAT_MEMORY) for i in range(20)]
        self.assertEqual(mp.score(found, fixture()), 0)
        self.assertEqual(mp.score([], fixture()), 100)

    def test_info_findings_cost_nothing(self):
        self.assertEqual(mp.score([finding("info", "uptime")], fixture()), 100)

    def test_memory_family_capped_at_30(self):
        found = [finding("critical", "swap"), finding("critical", "pressure"),
                 finding("critical", "hog:Chrome"), finding("critical", "hog:Slack"),
                 finding("critical", "hog:Xcode")]
        rows = mp.score_breakdown(found, fixture())
        family = sum(r["points"] for r in rows if r["key"].startswith(MEMORY_FAMILY))
        self.assertLessEqual(family, 30)
        self.assertGreater(family, 0)

    def test_cap_does_not_swallow_other_findings(self):
        mem = fixture()
        mem_only = [finding("critical", "swap"), finding("critical", "hog:a"),
                    finding("critical", "hog:b"), finding("critical", "hog:c")]
        with_disk = mem_only + [finding("critical", "disk")]
        self.assertLess(mp.score(with_disk, mem), mp.score(mem_only, mem))


class Parsers(unittest.TestCase):
    def test_pressure_levels(self):
        self.assertEqual(mp.parse_pressure_level(1), "normal")
        self.assertEqual(mp.parse_pressure_level(2), "warn")
        self.assertEqual(mp.parse_pressure_level(4), "critical")

    def test_pressure_garbage_is_none(self):
        for bad in (None, 0, 3, 99, "garbage", ""):
            self.assertIsNone(mp.parse_pressure_level(bad), bad)

    def test_therm_throttled(self):
        text = ("Note: No thermal warning level has been recorded\n"
                "Note: No performance warning level has been recorded\n"
                "CPU_Scheduler_Limit \t= 100\nCPU_Available_CPUs \t= 8\n"
                "CPU_Speed_Limit \t= 60\n")
        r = mp.parse_pmset_therm(text)
        self.assertEqual(r["speed_limit"], 60)
        self.assertTrue(r["throttled"])

    def test_therm_not_throttled(self):
        r = mp.parse_pmset_therm("CPU_Speed_Limit \t= 100\n")
        self.assertEqual(r["speed_limit"], 100)
        self.assertFalse(r["throttled"])

    def test_therm_empty_and_garbled(self):
        for text in ("", "   \n", "%%% not pmset output ###", None):
            r = mp.parse_pmset_therm(text or "")
            self.assertIsNone(r["speed_limit"], text)
            self.assertFalse(r["throttled"], text)

    def test_battery_present(self):
        text = ('+-o AppleSmartBattery  <class AppleSmartBattery>\n  {\n'
                '    "BatteryInstalled" = Yes\n    "CycleCount" = 312\n'
                '    "DesignCapacity" = 4380\n    "MaxCapacity" = 80\n'
                '    "AppleRawMaxCapacity" = 3504\n  }\n')
        r = mp.parse_battery(text)
        self.assertTrue(r["present"])
        self.assertEqual(r["cycle_count"], 312)
        self.assertIsInstance(r["capacity_pct"], int)
        self.assertAlmostEqual(r["capacity_pct"], 80, delta=1)

    def test_battery_absent(self):
        for text in ("", "garbled <<>>"):
            r = mp.parse_battery(text)
            self.assertFalse(r["present"])
            self.assertIsNone(r["cycle_count"])
            self.assertIsNone(r["capacity_pct"])
            self.assertIsNone(r["condition"])


class SignalFindings(unittest.TestCase):
    def test_thermal_throttled_warns(self):
        mem = fixture(thermal={"speed_limit": 60, "throttled": True})
        found = mp.check_thermal([], mem)
        self.assertEqual([f.sev for f in found], ["warn"])

    def test_thermal_silent_when_healthy(self):
        self.assertEqual(mp.check_thermal([], fixture()), [])

    def test_battery_worn_warns(self):
        mem = fixture(battery={"present": True, "cycle_count": 900, "capacity_pct": 70,
                               "condition": "Service Recommended"})
        self.assertEqual([f.sev for f in mp.check_battery([], mem)], ["warn"])

    def test_battery_silent_when_healthy_or_absent(self):
        healthy = fixture(battery={"present": True, "cycle_count": 50, "capacity_pct": 96,
                                   "condition": "Normal"})
        self.assertEqual(mp.check_battery([], healthy), [])
        self.assertEqual(mp.check_battery([], fixture()), [])


if __name__ == "__main__":
    unittest.main()


class AutomationContract(unittest.TestCase):
    def test_exit_status_codes(self):
        self.assertEqual(mp.exit_status([]), 0)
        self.assertEqual(mp.exit_status([finding("info", "uptime")]), 0)
        self.assertEqual(mp.exit_status([finding("warn", "swap")]), 1)
        self.assertEqual(mp.exit_status([finding("warn", "swap"), finding("critical", "disk")]), 2)
        self.assertEqual(mp.exit_status([finding("critical", "disk")]), 2)

    def test_blind_scan_is_unknown_not_healthy(self):
        self.assertEqual(mp.exit_status([], ["sensor: process table (ps)"]), 3)
        self.assertEqual(mp.exit_status([finding("warn", "swap")], ["x"]), 1)

    def test_warn_and_critical_cost_points(self):
        mem = fixture()
        self.assertEqual(mp.score([], mem), 100)
        w = 100 - mp.score([finding("warn", "thermal", mp.CAT_PROC)], mem)
        c = 100 - mp.score([finding("critical", "thermal", mp.CAT_PROC)], mem)
        self.assertGreater(w, 0)
        self.assertGreater(c, w)

    def test_metrics_exposition(self):
        payload = {"score": 76, "memory": fixture(swap_used_mb=1024.0),
                   "findings": [{"severity": "warn"}, {"severity": "info"}]}
        text = mp.metrics_text(payload)
        self.assertTrue(text.endswith("# EOF\n"))
        for name in ("macpulse_score", "macpulse_swap_used_bytes",
                     "macpulse_memory_pressure_level", "macpulse_findings"):
            self.assertIn(f"# TYPE {name} ", text)
            self.assertIn(f"# HELP {name} ", text)
        self.assertIn("macpulse_score 76", text)
        self.assertIn('macpulse_findings{severity="warn"} 1', text)
