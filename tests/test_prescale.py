from __future__ import annotations

from fleet.control.cron import Schedule
from fleet.control.jobs import JobSpec
from fleet.objects import Resources, TaskSpec
from fleet.prescale import Prescaler, queued_work


def schedule(every: int = 50) -> Schedule:
    job = JobSpec(
        name="batch",
        completions=1,
        parallelism=1,
        template=TaskSpec(name="tpl", needs=Resources(cpu=1, memory=1)),
    )
    return Schedule(name="batch", every=every, job=job)


class TestPrescaler:
    def test_capacity_rises_a_warmup_before_the_firing(self):
        prescaler = Prescaler(warmup=5)
        prescaler.plan([schedule()], demand_cpu=400, horizon=60)
        assert prescaler.capacity_at(100, 44) == 100
        assert prescaler.capacity_at(100, 45) == 500

    def test_capacity_returns_after_the_hold(self):
        prescaler = Prescaler(warmup=5, hold_after=3)
        prescaler.plan([schedule()], demand_cpu=400, horizon=60)
        assert prescaler.capacity_at(100, 52) == 500
        assert prescaler.capacity_at(100, 53) == 100

    def test_the_first_firing_clamps_at_zero(self):
        prescaler = Prescaler(warmup=5)
        prescaler.plan([schedule()], demand_cpu=400, horizon=10)
        assert prescaler.capacity_at(100, 0) == 500


class TestQueuedWork:
    def test_ample_capacity_queues_nothing(self):
        assert queued_work(500, 5, 20, lambda tick: 1000) == 0

    def test_scarce_capacity_integrates_the_backlog(self):
        assert queued_work(900, 0, 10, lambda tick: 300) == 900

    def test_no_burst_no_queue(self):
        assert queued_work(0, 5, 20, lambda tick: 1) == 0
