from __future__ import annotations

from fleet.audit import Journal
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.pressureloop import PressureLoop
from fleet.sched.qos import Ask, PressureNode
from fleet.store import Store
from fleet.taintevict import GracedToleration, TaintEvictor


def rig() -> tuple[Store, PressureNode, PressureLoop]:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    node = PressureNode(node=store.get_node("n0"))
    node.admit(
        Ask("burster", Resources(cpu=300, memory=300), Resources(cpu=900, memory=900))
    )
    for name in ("graced", "fragile"):
        task = Task(spec=TaskSpec(name=name, needs=Resources(cpu=100, memory=100)))
        task.bound_to("n0")
        store.add_task(task)
    evictor = TaintEvictor()
    evictor.tolerate("graced", GracedToleration(key="pressure", seconds=5))
    loop = PressureLoop(evictor=evictor, journal=Journal())
    return store, node, loop


class TestTheLoop:
    def test_calm_nodes_stay_untainted(self):
        store, node, loop = rig()
        assert loop.observe(store, node, now=0) == []

    def test_pressure_taints_and_the_fragile_leave_first(self):
        store, node, loop = rig()
        node.burst("burster", Resources(cpu=900, memory=900))
        node.tenants[0].using = Resources(cpu=1100, memory=1100)
        actions = loop.observe(store, node, now=0)
        assert "n0 tainted under pressure" in actions
        assert "fragile evicted after grace" in actions
        assert store.get_task("graced").is_active()

    def test_the_graced_tenant_gets_its_notice(self):
        store, node, loop = rig()
        node.tenants[0].using = Resources(cpu=1100, memory=1100)
        loop.observe(store, node, now=0)
        actions = loop.observe(store, node, now=5)
        assert "graced evicted after grace" in actions

    def test_relief_lifts_the_taint_before_the_grace_expires(self):
        store, node, loop = rig()
        node.tenants[0].using = Resources(cpu=1100, memory=1100)
        loop.observe(store, node, now=0)
        node.tenants[0].using = Resources(cpu=300, memory=300)
        actions = loop.observe(store, node, now=2)
        assert "n0 pressure lifted" in actions
        assert store.get_task("graced").is_active()

    def test_the_journal_tells_one_story(self):
        store, node, loop = rig()
        node.tenants[0].using = Resources(cpu=1100, memory=1100)
        loop.observe(store, node, now=0)
        loop.observe(store, node, now=5)
        verbs = [decision.verb for decision in loop.journal.decisions]
        assert verbs[0] == "taint"
        assert "evict" in verbs
