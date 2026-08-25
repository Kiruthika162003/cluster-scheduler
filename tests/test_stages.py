from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.objects import Resources, Task, TaskSpec
from fleet.stages import Stage, StageKeeper
from fleet.store import Store

PIPELINE = (Stage("migrate"), Stage("warm", attempts_allowed=2), Stage("serve"))


def bound_store() -> Store:
    store = Store()
    task = Task(spec=TaskSpec(name="api", needs=Resources(cpu=100, memory=100)))
    task.bound_to("n0")
    store.add_task(task)
    return store


class TestAdvancing:
    def test_stages_run_in_declared_order(self):
        store = bound_store()
        keeper = StageKeeper()
        keeper.declare("api", PIPELINE)
        assert keeper.begin("api", now=0) == "migrate"
        assert keeper.complete(store, "api", now=4) == "warm"
        keeper.begin("api", now=4)
        assert keeper.complete(store, "api", now=9) == "serve"

    def test_the_last_stage_promotes_to_running(self):
        store = bound_store()
        keeper = StageKeeper()
        keeper.declare("api", (Stage("only"),))
        keeper.begin("api", now=0)
        assert keeper.complete(store, "api", now=2) == "running"
        assert store.get_task("api").phase == "Running"

    def test_durations_are_recorded_per_stage(self):
        store = bound_store()
        keeper = StageKeeper()
        keeper.declare("api", PIPELINE)
        keeper.begin("api", now=0)
        keeper.complete(store, "api", now=4)
        keeper.begin("api", now=4)
        keeper.complete(store, "api", now=9)
        report = keeper.stage_report("api")
        assert "migrate=4" in report and "warm=5" in report

    def test_declaring_no_stages_is_refused(self):
        with pytest.raises(Invalid):
            StageKeeper().declare("api", ())


class TestFailure:
    def test_retries_stay_inside_the_stage(self):
        store = bound_store()
        keeper = StageKeeper()
        keeper.declare("api", PIPELINE)
        keeper.begin("api", now=0)
        told = keeper.fail(store, "api", now=1)
        assert told == "retrying migrate, attempt 2"
        assert store.get_task("api").phase == "Bound"

    def test_exhaustion_fails_with_the_stage_named(self):
        store = bound_store()
        keeper = StageKeeper()
        keeper.declare("api", PIPELINE)
        keeper.complete(store, "api", now=1)
        keeper.begin("api", now=1)
        keeper.fail(store, "api", now=2)
        told = keeper.fail(store, "api", now=3)
        assert told == "failed in warm"
        assert store.get_task("api").phase == "Failed"
        assert "failed in warm" in keeper.stage_report("api")

    def test_completing_a_finished_pipeline_is_refused(self):
        store = bound_store()
        keeper = StageKeeper()
        keeper.declare("api", (Stage("only"),))
        keeper.complete(store, "api", now=1)
        with pytest.raises(Invalid):
            keeper.complete(store, "api", now=2)
