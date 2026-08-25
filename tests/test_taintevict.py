from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store
from fleet.taintevict import GracedToleration, TaintEvictor


def housed(names: list[str]) -> Store:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=4000, memory=4000)))
    for name in names:
        task = Task(spec=TaskSpec(name=name, needs=Resources(cpu=100, memory=100)))
        task.bound_to("n0")
        store.add_task(task)
    return store


class TestEviction:
    def test_an_untolerant_tenant_leaves_immediately(self):
        store = housed(["fragile"])
        evictor = TaintEvictor()
        evictor.taint("n0", "pressure", now=10)
        assert evictor.sweep(store, now=10) == ["fragile"]

    def test_a_graced_tenant_stays_its_seconds(self):
        store = housed(["graced"])
        evictor = TaintEvictor()
        evictor.tolerate("graced", GracedToleration(key="pressure", seconds=5))
        evictor.taint("n0", "pressure", now=10)
        assert evictor.sweep(store, now=14) == []
        assert evictor.sweep(store, now=15) == ["graced"]

    def test_the_clock_starts_at_the_taint_not_the_sweep(self):
        store = housed(["graced"])
        evictor = TaintEvictor()
        evictor.tolerate("graced", GracedToleration(key="pressure", seconds=5))
        evictor.taint("n0", "pressure", now=10)
        assert evictor.sweep(store, now=20) == ["graced"]

    def test_untainting_cancels_the_notice(self):
        store = housed(["graced"])
        evictor = TaintEvictor()
        evictor.tolerate("graced", GracedToleration(key="pressure", seconds=5))
        evictor.taint("n0", "pressure", now=10)
        evictor.untaint("n0", "pressure")
        assert evictor.sweep(store, now=30) == []

    def test_mixed_tenants_leave_on_their_own_schedules(self):
        store = housed(["fragile", "graced"])
        evictor = TaintEvictor()
        evictor.tolerate("graced", GracedToleration(key="pressure", seconds=8))
        evictor.taint("n0", "pressure", now=0)
        assert evictor.sweep(store, now=0) == ["fragile"]
        assert evictor.sweep(store, now=7) == []
        assert evictor.sweep(store, now=8) == ["graced"]

    def test_other_taint_keys_do_not_borrow_grace(self):
        store = housed(["graced"])
        evictor = TaintEvictor()
        evictor.tolerate("graced", GracedToleration(key="pressure", seconds=50))
        evictor.taint("n0", "decommission", now=0)
        assert evictor.sweep(store, now=0) == ["graced"]
