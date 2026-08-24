from __future__ import annotations

import pytest

from fleet.errors import Unschedulable
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.preempt import Preemptor, requeue_evicted
from fleet.store import Store


def node(name: str, cpu: int = 1000) -> Node:
    return Node(name=name, capacity=Resources(cpu=cpu, memory=1000))


def bound(name: str, node_name: str, cpu: int, priority: int) -> Task:
    task = Task(
        spec=TaskSpec(name=name, needs=Resources(cpu=cpu, memory=100), priority=priority)
    )
    task.bound_to(node_name)
    return task


def wanted(name: str, cpu: int, priority: int) -> Task:
    return Task(
        spec=TaskSpec(name=name, needs=Resources(cpu=cpu, memory=100), priority=priority)
    )


class TestPlans:
    def test_no_eviction_needed_makes_an_empty_plan(self):
        preemptor = Preemptor()
        plan = preemptor.plan_for_node(wanted("w", 200, 5), node("n"), [])
        assert plan is not None and plan.victims == () and plan.cost == 0

    def test_one_victim_suffices_when_it_frees_enough(self):
        active = [
            bound("cheap", "n", 400, 1),
            bound("mid", "n", 400, 2),
        ]
        preemptor = Preemptor()
        plan = preemptor.plan_for_node(wanted("w", 500, 5), node("n"), active)
        assert plan.victims == ("cheap",)

    def test_victims_accumulate_cheapest_first_until_the_fit(self):
        active = [
            bound("cheap", "n", 400, 1),
            bound("mid", "n", 400, 2),
        ]
        preemptor = Preemptor()
        plan = preemptor.plan_for_node(wanted("w", 900, 5), node("n"), active)
        assert plan.victims == ("cheap", "mid")

    def test_equal_priority_is_never_a_victim(self):
        active = [bound("peer", "n", 900, 5)]
        preemptor = Preemptor()
        assert preemptor.plan_for_node(wanted("w", 500, 5), node("n"), active) is None

    def test_the_cheapest_plan_wins_across_nodes(self):
        store = Store()
        store.add_node(node("a"))
        store.add_node(node("b"))
        store.add_task(bound("costly", "a", 900, 4))
        store.add_task(bound("cheap", "b", 900, 1))
        preemptor = Preemptor()
        plan = preemptor.make_room(store, wanted("w", 500, 5))
        assert plan.node == "b" and plan.victims == ("cheap",)

    def test_fewest_victims_breaks_a_cost_tie(self):
        store = Store()
        store.add_node(node("a"))
        store.add_node(node("b"))
        store.add_task(bound("one", "a", 400, 1))
        store.add_task(bound("two", "a", 500, 1))
        store.add_task(bound("lone", "b", 900, 2))
        preemptor = Preemptor()
        plan = preemptor.make_room(store, wanted("w", 800, 5))
        assert plan.node == "b" and plan.victims == ("lone",)


class TestEviction:
    def test_make_room_evicts_and_counts(self):
        store = Store()
        store.add_node(node("n"))
        store.add_task(bound("v", "n", 900, 1))
        preemptor = Preemptor()
        preemptor.make_room(store, wanted("w", 500, 5))
        assert store.get_task("v").phase == "Evicted"
        assert preemptor.evicted == 1

    def test_an_impossible_ask_raises(self):
        store = Store()
        store.add_node(node("n"))
        store.add_task(bound("king", "n", 900, 9))
        with pytest.raises(Unschedulable):
            Preemptor().make_room(store, wanted("w", 500, 5))

    def test_requeue_returns_evicted_to_pending(self):
        store = Store()
        store.add_node(node("n"))
        store.add_task(bound("v", "n", 900, 1))
        Preemptor().make_room(store, wanted("w", 500, 5))
        assert requeue_evicted(store) == 1
        assert store.get_task("v").phase == "Pending"
        assert store.get_task("v").node is None

    def test_requeue_of_a_quiet_store_does_nothing(self):
        store = Store()
        assert requeue_evicted(store) == 0
