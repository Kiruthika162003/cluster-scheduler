from __future__ import annotations

import pytest

from fleet.metering import Meter
from fleet.objects import Resources, Task, TaskSpec
from fleet.store import Store


def running(name: str, namespace: str, cpu: int) -> Task:
    task = Task(
        spec=TaskSpec(
            name=name, needs=Resources(cpu=cpu, memory=cpu), namespace=namespace
        )
    )
    task.bound_to("n0")
    task.phase = "Running"
    return task


def metered_store() -> Store:
    store = Store()
    store.add_task(running("a", "search", 300))
    store.add_task(running("b", "ads", 100))
    pending = Task(
        spec=TaskSpec(
            name="waiting", needs=Resources(cpu=900, memory=900), namespace="ads"
        )
    )
    store.add_task(pending)
    return store


class TestMeter:
    def test_only_running_work_is_metered(self):
        meter = Meter()
        meter.sample(metered_store())
        assert meter.cpu_ticks == {"search": 300, "ads": 100}

    def test_integrals_accumulate_over_ticks(self):
        meter = Meter()
        store = metered_store()
        for _ in range(5):
            meter.sample(store)
        assert meter.cpu_ticks["search"] == 1500
        assert meter.task_ticks["search"] == 5

    def test_shares_sum_to_one(self):
        meter = Meter()
        meter.sample(metered_store())
        total = sum(meter.share_of(space) for space in meter.cpu_ticks)
        assert total == pytest.approx(1.0)

    def test_a_mid_run_stop_stops_the_meter(self):
        meter = Meter()
        store = metered_store()
        meter.sample(store)
        store.get_task("a").phase = "Succeeded"
        meter.sample(store)
        assert meter.cpu_ticks["search"] == 300
        assert meter.cpu_ticks["ads"] == 200

    def test_the_statement_reads_per_namespace(self):
        meter = Meter()
        meter.sample(metered_store())
        page = meter.statement()
        assert "search" in page and "75.0%" in page

    def test_an_idle_meter_says_so(self):
        meter = Meter()
        meter.sample(Store())
        assert "nothing ran" in meter.statement()
        assert meter.share_of("anything") == 0.0
