from __future__ import annotations

import pytest

from fleet.control.deploy import DeploySpec
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sim.cluster import Script, Sim
from fleet.store import Store
from fleet.verify import assert_clean, violations


def small(name: str = "t", cpu: int = 100) -> Task:
    return Task(spec=TaskSpec(name=name, needs=Resources(cpu=cpu, memory=cpu)))


class TestInvariants:
    def test_a_clean_store_reports_nothing(self):
        store = Store()
        store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
        task = small()
        task.bound_to("n0")
        store.add_task(task)
        assert violations(store) == []

    def test_a_bound_task_without_a_node_is_named(self):
        store = Store()
        task = small()
        task.phase = "Bound"
        store.add_task(task)
        assert "no node" in violations(store)[0]

    def test_a_task_on_a_ghost_node_is_named(self):
        store = Store()
        task = small()
        task.bound_to("ghost")
        store.add_task(task)
        assert "does not exist" in violations(store)[0]

    def test_a_pending_task_holding_a_node_is_named(self):
        store = Store()
        store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
        task = small()
        task.bound_to("n0")
        task.phase = "Pending"
        store.add_task(task)
        assert "still holds" in violations(store)[0]

    def test_an_overcommitted_node_is_measured(self):
        store = Store()
        store.add_node(Node(name="n0", capacity=Resources(cpu=100, memory=100)))
        for name in ("a", "b"):
            task = small(name, cpu=80)
            task.bound_to("n0")
            store.add_task(task)
        told = violations(store)
        assert "overcommitted by 60m" in told[0]

    def test_a_finished_task_holding_a_node_is_named(self):
        store = Store()
        store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
        task = small()
        task.bound_to("n0")
        task.phase = "Succeeded"
        store.add_task(task)
        assert "Succeeded but still holds" in violations(store)[0]

    def test_violations_arrive_in_families(self):
        store = Store()
        one = small("a")
        one.phase = "Bound"
        two = small("b")
        two.bound_to("ghost")
        store.add_task(one)
        store.add_task(two)
        assert len(violations(store)) == 2

    def test_assert_clean_raises_with_every_sentence(self):
        store = Store()
        task = small()
        task.phase = "Bound"
        store.add_task(task)
        with pytest.raises(AssertionError):
            assert_clean(store)


class TestSimStaysClean:
    def test_a_stormy_sim_holds_every_invariant_every_tick(self):
        sim = Sim(script=Script(silences={"n1": (10, 40)}))
        sim.add_nodes(3)
        sim.deploys.append(
            DeploySpec(
                name="web",
                replicas=6,
                template=TaskSpec(name="tpl", needs=Resources(cpu=300, memory=300)),
            )
        )
        for _ in range(60):
            sim.tick()
            assert_clean(sim.store)
