"""idle_sessions, swap_growth and Finding.auto_fix — pure functions on fixtures."""
import getpass
import unittest

from _loader import load_macpulse

mp = load_macpulse()
H = 3600
ME = getpass.getuser()
CLAUDE = "/Users/x/.local/share/claude/native-binary/claude --resume"


def proc(pid, elapsed_h, cpu_s=0, cmd=CLAUDE, user=ME, ppid=1):
    return mp.Proc(pid, ppid, 0.0, 100_000, elapsed_h * H, cpu_s, user, cmd)


class IdleSessions(unittest.TestCase):
    def pids(self, procs, own=()):
        return sorted(p.pid for p in mp.idle_sessions(procs, set(own)))

    def test_old_and_quiet_is_selected(self):
        self.assertEqual(self.pids([proc(10, 20, cpu_s=5)]), [10])

    def test_young_session_is_kept(self):
        self.assertEqual(self.pids([proc(10, 11, cpu_s=0)]), [])

    def test_twelve_hours_is_the_boundary(self):
        self.assertEqual(self.pids([proc(10, 12, cpu_s=0)]), [10])

    def test_busy_session_is_kept(self):
        # 2 % of 20 h of wall clock is far above the 0.5 % idle bar
        self.assertEqual(self.pids([proc(10, 20, cpu_s=int(20 * H * 0.02))]), [])

    def test_cpu_share_boundary(self):
        just_under = int(20 * H * 0.0049)
        just_over = int(20 * H * 0.0051)
        self.assertEqual(self.pids([proc(1, 20, cpu_s=just_under)]), [1])
        self.assertEqual(self.pids([proc(2, 20, cpu_s=just_over)]), [])

    def test_own_session_and_ancestors_never_selected(self):
        procs = [proc(10, 30), proc(11, 30), proc(12, 30)]
        self.assertEqual(self.pids(procs, own={10, 12}), [11])

    def test_other_users_and_other_programs_ignored(self):
        procs = [proc(10, 30, user="someone_else"),
                 proc(11, 30, cmd="/usr/bin/python3 server.py"),
                 proc(12, 30)]
        self.assertEqual(self.pids(procs), [12])

    def test_returns_proc_objects(self):
        out = mp.idle_sessions([proc(10, 30)], set())
        self.assertIsInstance(out[0], mp.Proc)

    def test_none_own_pids_is_tolerated(self):
        self.assertEqual(len(mp.idle_sessions([proc(10, 30)], None)), 1)


class SwapGrowth(unittest.TestCase):
    NOW = 1_000_000.0

    def samples(self, *pairs):
        """pairs of (minutes_ago, gb)"""
        return [(self.NOW - m * 60, gb) for m, gb in pairs]

    def test_two_gib_in_five_minutes_hits(self):
        g = mp.swap_growth(self.samples((5, 3.0), (0, 5.0)), self.NOW)
        self.assertEqual(g["delta_gb"], 2.0)
        self.assertAlmostEqual(g["minutes"], 5.0, places=1)

    def test_half_gib_is_ignored(self):
        self.assertIsNone(mp.swap_growth(self.samples((5, 3.0), (0, 3.5)), self.NOW))

    def test_growth_older_than_window_is_ignored(self):
        # +3 GiB happened 40 minutes ago; the last half hour is flat
        s = self.samples((45, 1.0), (40, 4.0), (20, 4.0), (0, 4.1))
        self.assertIsNone(mp.swap_growth(s, self.NOW))

    def test_empty_and_single_sample(self):
        self.assertIsNone(mp.swap_growth([], self.NOW))
        self.assertIsNone(mp.swap_growth(self.samples((0, 9.0)), self.NOW))

    def test_shrinking_swap_is_not_growth(self):
        self.assertIsNone(mp.swap_growth(self.samples((10, 6.0), (0, 2.0)), self.NOW))

    def test_none_samples_are_skipped(self):
        s = self.samples((10, None), (5, 1.0), (0, 2.5))
        self.assertEqual(mp.swap_growth(s, self.NOW)["delta_gb"], 1.5)

    def test_unsorted_input_is_handled(self):
        s = list(reversed(self.samples((10, 1.0), (5, 1.5), (0, 3.0))))
        self.assertEqual(mp.swap_growth(s, self.NOW)["delta_gb"], 2.0)


class AutoFix(unittest.TestCase):
    def test_default_is_true(self):
        f = mp.Finding("warn", "x", mp.CAT_MEMORY, "x.t", "x.d", {})
        self.assertIs(f.auto_fix, True)

    def test_idle_finding_is_not_auto_fix(self):
        procs = [proc(10, 30, cpu_s=1)]
        found = mp.check_idle_sessions(procs, {})
        self.assertEqual([f.key for f in found], ["ai:idle"])
        self.assertIs(found[0].auto_fix, False)
        self.assertTrue(found[0].fix)

    def test_no_idle_sessions_no_finding(self):
        self.assertEqual(mp.check_idle_sessions([proc(10, 1)], {}), [])


if __name__ == "__main__":
    unittest.main()


class RoundFiveRegressions(unittest.TestCase):
    """Refuter round 5: busy-now sessions, look-alike paths, pid reuse, blind swap."""

    def test_session_busy_right_now_is_kept(self):
        p = proc(10, 20, cpu_s=0)
        p.cpu = 95.0
        self.assertEqual(mp.idle_sessions([p], set()), [])

    def test_editor_holding_a_claude_path_is_not_a_session(self):
        p = proc(10, 30, cmd="/usr/bin/vim /Users/x/notes/claude ")
        self.assertEqual(mp.idle_sessions([p], set()), [])

    def test_terminator_skips_a_recycled_pid(self):
        from unittest import mock
        sent = []
        cp = mp.subprocess.CompletedProcess([], 0, "/usr/bin/some-other-program\n", "")
        with mock.patch.object(mp.subprocess, "run", return_value=cp), \
                mock.patch.object(mp.os, "kill", side_effect=lambda pid, sig: sent.append(pid)):
            mp._terminator([4242], {4242: CLAUDE})("en")
        self.assertEqual(sent, [])

    def test_terminator_signals_the_same_process(self):
        from unittest import mock
        sent = []
        cp = mp.subprocess.CompletedProcess([], 0, CLAUDE + "\n", "")
        with mock.patch.object(mp.subprocess, "run", return_value=cp), \
                mock.patch.object(mp.os, "kill", side_effect=lambda pid, sig: sent.append(pid)):
            mp._terminator([4242], {4242: CLAUDE})("en")
        self.assertEqual(sent, [4242])

    def test_blind_swap_scan_makes_no_growth_claim(self):
        mem = {"swap_used_mb": 0.0, "sensors_failed": ["swap (sysctl vm.swapusage)"]}
        self.assertEqual(mp.check_swap_growth([], mem), [])

    def test_blind_swap_is_stored_as_unknown(self):
        import time
        mem = {"total": 8 * 1024 ** 3, "swap_used_mb": 0.0, "swap_total_mb": 0.0,
               "free_pct": 50, "disk_free": 50 * 1024 ** 3,
               "sensors_failed": ["swap (sysctl vm.swapusage)"]}
        t0 = time.time() - 1
        mp.hist.record(90, mem, [])
        self.assertEqual([s for s in mp.hist.swap_samples(t0)], [])


class RoundSixRegressions(unittest.TestCase):
    def test_session_whose_child_is_busy_is_kept(self):
        host = proc(10, 20, cpu_s=0)
        child = mp.Proc(11, 10, 85.0, 50_000, 600, 500, ME, "/bin/zsh -c pytest")
        self.assertEqual(mp.idle_sessions([host, child], set()), [])

    def test_session_with_quiet_children_is_still_idle(self):
        host = proc(10, 20, cpu_s=0)
        child = mp.Proc(11, 10, 0.0, 50_000, 20 * H, 1, ME, "node mcp-server")
        self.assertEqual([p.pid for p in mp.idle_sessions([host, child], set())], [10])


class ProcessTreeCycles(unittest.TestCase):
    def test_self_parented_pid_does_not_hang(self):
        a = mp.Proc(1, 1, 0.0, 1, 10, 0, ME, "/sbin/launchd")
        b = mp.Proc(5, 1, 0.0, 1, 10, 0, ME, "x")
        self.assertEqual(sorted(p.pid for p in mp.descendants([a, b], 1)), [5])

    def test_two_pid_cycle_does_not_hang(self):
        a = mp.Proc(7, 8, 0.0, 1, 10, 0, ME, "a")
        b = mp.Proc(8, 7, 0.0, 1, 10, 0, ME, "b")
        self.assertEqual(sorted(p.pid for p in mp.descendants([a, b], 7)), [8])
