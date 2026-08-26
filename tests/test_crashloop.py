from __future__ import annotations

from fleet.crashloop import (
    BACKOFF_CAP,
    HEALTHY_RESET,
    CrashTracker,
)


class TestBackoff:
    def test_the_wait_doubles_to_the_cap(self):
        tracker = CrashTracker()
        waits = [tracker.crashed("web", now=tick * 100) for tick in range(8)]
        assert waits == [2, 4, 8, 16, 32, 64, 64, 64]

    def test_restarts_wait_out_the_backoff(self):
        tracker = CrashTracker()
        tracker.crashed("web", now=0)
        assert not tracker.may_restart("web", now=1)
        assert tracker.may_restart("web", now=2)

    def test_a_healthy_stretch_resets_the_curve(self):
        tracker = CrashTracker()
        for tick in range(4):
            tracker.crashed("web", now=tick * 100)
        tracker.started("web", now=500)
        wait = tracker.crashed("web", now=500 + HEALTHY_RESET)
        assert wait == 2

    def test_a_short_healthy_gasp_does_not_reset(self):
        tracker = CrashTracker()
        for tick in range(4):
            tracker.crashed("web", now=tick * 100)
        tracker.started("web", now=500)
        wait = tracker.crashed("web", now=505)
        assert wait == 32


class TestVerdicts:
    def test_the_loop_gets_its_name_at_the_threshold(self):
        tracker = CrashTracker()
        for tick in range(4):
            tracker.crashed("web", now=tick)
        assert tracker.verdict("web") == "crashing (4 in a row)"
        tracker.crashed("web", now=10)
        assert tracker.verdict("web") == "CrashLoopBackOff"

    def test_the_untouched_are_healthy(self):
        assert CrashTracker().verdict("quiet") == "healthy"


class TestTheArithmetic:
    def test_backoff_caps_the_cost_of_a_broken_task(self):
        tracker = CrashTracker()
        restarts = 0
        now = 0
        while now < 1000:
            if tracker.may_restart("web", now):
                tracker.crashed("web", now)
                restarts += 1
            now += 1
        assert restarts == 20
        assert 1000 // BACKOFF_CAP < restarts < 1000


class TestStorms:
    def test_two_crashers_are_not_a_storm(self):
        tracker = CrashTracker()
        for task in ("a", "b"):
            tracker.crashed(task, now=0)
            tracker.crashed(task, now=1)
        assert tracker.storm(now=2) is None

    def test_a_shared_cause_is_named(self):
        tracker = CrashTracker()
        for task in ("a", "b", "c"):
            tracker.register(task, node="n7", image="app:v2")
            tracker.crashed(task, now=0)
            tracker.crashed(task, now=1)
        report = tracker.storm(now=2)
        assert report == "storm: 3 tasks crashing, all sharing image=app:v2"

    def test_no_shared_cause_says_check_the_fleet(self):
        tracker = CrashTracker()
        for index, task in enumerate(("a", "b", "c")):
            tracker.register(task, node=f"n{index}", image=f"app:v{index}")
            tracker.crashed(task, now=0)
            tracker.crashed(task, now=1)
        report = tracker.storm(now=2)
        assert "no single shared cause" in report

    def test_old_crashers_age_out_of_the_storm(self):
        tracker = CrashTracker()
        for task in ("a", "b", "c"):
            tracker.register(task, node="n7")
            tracker.crashed(task, now=0)
            tracker.crashed(task, now=1)
        assert tracker.storm(now=2) is not None
        assert tracker.storm(now=50) is None
