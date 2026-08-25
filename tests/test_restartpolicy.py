from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.objects import Resources, Task, TaskSpec
from fleet.restartpolicy import RestartKeeper
from fleet.store import Store


def finished(name: str, phase: str) -> Store:
    store = Store()
    task = Task(spec=TaskSpec(name=name, needs=Resources(cpu=1, memory=1)))
    task.phase = phase
    store.add_task(task)
    return store


class TestPolicies:
    def test_unknown_policies_are_refused(self):
        with pytest.raises(Invalid):
            RestartKeeper().assign("t", "sometimes")

    def test_always_restarts_success_too(self):
        store = finished("svc", "Succeeded")
        keeper = RestartKeeper()
        keeper.assign("svc", "always")
        keeper.sweep(store, now=0)
        assert store.get_task("svc").phase == "Pending"
        assert store.get_task("svc").restarts == 1

    def test_on_failure_restarts_only_failure(self):
        keeper = RestartKeeper()
        keeper.assign("batch", "on-failure")
        failed = finished("batch", "Failed")
        keeper.sweep(failed, now=0)
        assert failed.get_task("batch").phase == "Pending"
        done = finished("batch", "Succeeded")
        keeper.sweep(done, now=0)
        assert done.get_task("batch").phase == "Succeeded"

    def test_never_leaves_both_ends_alone(self):
        keeper = RestartKeeper()
        keeper.assign("migration", "never")
        for phase in ("Succeeded", "Failed"):
            store = finished("migration", phase)
            keeper.sweep(store, now=0)
            assert store.get_task("migration").phase == phase

    def test_unassigned_tasks_are_untouched(self):
        store = finished("stray", "Failed")
        RestartKeeper().sweep(store, now=0)
        assert store.get_task("stray").phase == "Failed"


class TestTheRecord:
    def test_restarts_and_refusals_both_reach_the_log(self):
        keeper = RestartKeeper()
        keeper.assign("svc", "always")
        keeper.assign("migration", "never")
        store = finished("svc", "Failed")
        migration = Task(
            spec=TaskSpec(name="migration", needs=Resources(cpu=1, memory=1))
        )
        migration.phase = "Failed"
        store.add_task(migration)
        keeper.sweep(store, now=5)
        assert any("always restarts it" in line for line in keeper.log)
        assert any("policy never" in line for line in keeper.log)

    def test_the_refusal_is_logged_once_not_every_sweep(self):
        keeper = RestartKeeper()
        keeper.assign("migration", "never")
        store = finished("migration", "Failed")
        keeper.sweep(store, now=0)
        keeper.sweep(store, now=1)
        stays = [line for line in keeper.log if "stays" in line]
        assert len(stays) == 1
