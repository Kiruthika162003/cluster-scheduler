from __future__ import annotations

import pytest

from fleet.control.cron import Cron, Schedule
from fleet.control.jobs import JobSpec
from fleet.errors import Invalid
from fleet.objects import Resources, TaskSpec


def job(name: str = "backup") -> JobSpec:
    return JobSpec(
        name=name,
        completions=1,
        parallelism=1,
        template=TaskSpec(name="tpl", needs=Resources(cpu=10, memory=10)),
    )


def schedule(policy: str = "one-shot", every: int = 10) -> Schedule:
    return Schedule(name="backup", every=every, job=job(), missed_policy=policy)


class TestSchedule:
    def test_the_period_must_be_positive(self):
        with pytest.raises(Invalid):
            Schedule(name="s", every=0, job=job())

    def test_unknown_policies_are_refused(self):
        with pytest.raises(Invalid):
            Schedule(name="s", every=5, job=job(), missed_policy="hope")

    def test_due_at_follows_the_period(self):
        held = schedule(every=10)
        assert held.due_at(0) and held.due_at(20)
        assert not held.due_at(15)


class TestOnTime:
    def test_a_wakeful_cron_fires_on_the_period(self):
        cron = Cron(schedules=[schedule()])
        fired = []
        for now in range(21):
            fired.extend(cron.tick(now))
        assert fired == ["backup@0", "backup@10", "backup@20"]

    def test_off_period_ticks_fire_nothing(self):
        cron = Cron(schedules=[schedule()])
        cron.tick(0)
        assert cron.tick(3) == []


class TestMissedWindows:
    def wake_late(self, policy: str) -> Cron:
        cron = Cron(schedules=[schedule(policy)])
        cron.tick(0)
        cron.tick(35)
        return cron

    def test_skip_forgets_the_missed(self):
        cron = self.wake_late("skip")
        assert [when for when, _ in cron.launches] == [0]
        assert cron.skipped == 3

    def test_catch_up_runs_them_all(self):
        cron = self.wake_late("catch-up")
        assert [when for when, _ in cron.launches] == [0, 10, 20, 30]

    def test_one_shot_runs_only_the_latest(self):
        cron = self.wake_late("one-shot")
        assert [when for when, _ in cron.launches] == [0, 30]
        assert cron.skipped == 2

    def test_waking_on_a_due_tick_runs_it_once(self):
        cron = Cron(schedules=[schedule("one-shot")])
        cron.tick(0)
        fired = cron.tick(30)
        assert fired == ["backup@20", "backup@30"]

    def test_policies_are_per_schedule(self):
        eager = Schedule(name="warm", every=10, job=job("warm"), missed_policy="skip")
        careful = Schedule(
            name="backup", every=10, job=job(), missed_policy="catch-up"
        )
        cron = Cron(schedules=[careful, eager])
        cron.tick(0)
        cron.tick(35)
        backups = [when for when, name in cron.launches if name == "backup"]
        warms = [when for when, name in cron.launches if name == "warm"]
        assert backups == [0, 10, 20, 30]
        assert warms == [0]
