from __future__ import annotations

from fleet.burnin import FENCE, BurnIn
from fleet.objects import Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.store import Store


def production_task(name: str = "web") -> Task:
    return Task(spec=TaskSpec(name=name, needs=Resources(cpu=100, memory=100)))


class TestJoining:
    def test_a_joiner_arrives_fenced(self):
        store = Store()
        burnin = BurnIn()
        node = burnin.join(store, "fresh", cpu=1000, now=0)
        assert node.taints[0].key == FENCE

    def test_production_cannot_land_on_a_fenced_node(self):
        store = Store()
        burnin = BurnIn()
        burnin.join(store, "fresh", cpu=1000, now=0)
        task = production_task()
        store.add_task(task)
        placed, stuck = Scheduler().schedule_pending(store)
        assert placed == 0 and stuck == 1

    def test_canaries_tolerate_the_fence(self):
        store = Store()
        burnin = BurnIn()
        burnin.join(store, "fresh", cpu=1000, now=0)
        canary = burnin.canary_task("fresh", 0)
        store.add_task(canary)
        placed, _ = Scheduler().schedule_pending(store)
        assert placed == 1
        assert store.get_task("canary-fresh-0").node == "fresh"


class TestVerdicts:
    def test_a_clean_window_lifts_the_fence(self):
        store = Store()
        burnin = BurnIn(probation=5)
        burnin.join(store, "fresh", cpu=1000, now=0)
        told = burnin.sweep(store, now=5)
        assert told == ["fresh graduated after 5 clean ticks"]
        assert store.get_node("fresh").taints == ()
        task = production_task()
        store.add_task(task)
        placed, _ = Scheduler().schedule_pending(store)
        assert placed == 1

    def test_a_failed_canary_rejects_the_node_whole(self):
        store = Store()
        burnin = BurnIn(probation=5)
        burnin.join(store, "lemon", cpu=1000, now=0)
        canary = burnin.canary_task("lemon", 0)
        store.add_task(canary)
        Scheduler().schedule_pending(store)
        burnin.note_canary_failure("lemon")
        told = burnin.sweep(store, now=3)
        assert told == ["lemon rejected in burn-in, production untouched"]
        assert "lemon" not in store.nodes
        assert "canary-lemon-0" not in store.tasks

    def test_the_probation_clock_is_not_rushed(self):
        store = Store()
        burnin = BurnIn(probation=5)
        burnin.join(store, "fresh", cpu=1000, now=0)
        assert burnin.sweep(store, now=4) == []
        assert store.get_node("fresh").taints != ()

    def test_ledgers_hold_the_verdicts(self):
        store = Store()
        burnin = BurnIn(probation=2)
        burnin.join(store, "good", cpu=1000, now=0)
        burnin.join(store, "bad", cpu=1000, now=0)
        burnin.note_canary_failure("bad")
        burnin.sweep(store, now=2)
        assert burnin.graduated == ["good"]
        assert burnin.rejected == ["bad"]
