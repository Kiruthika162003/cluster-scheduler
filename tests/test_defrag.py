from __future__ import annotations

from collections import Counter

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.defrag import Rebalancer
from fleet.store import Store


def cluster(nodes: int = 5) -> Store:
    store = Store()
    for number in range(nodes):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    return store


def sliver_city() -> Store:
    store = cluster()
    for number in range(5):
        task = Task(
            spec=TaskSpec(name=f"t{number}", needs=Resources(cpu=400, memory=400))
        )
        task.bound_to(f"n{number}")
        store.add_task(task)
    return store


class TestLargestPlaceable:
    def test_an_empty_cluster_offers_a_whole_node(self):
        rebalancer = Rebalancer(budget=0)
        assert rebalancer.largest_placeable(cluster()) == 1000

    def test_slivers_cap_the_offer(self):
        assert Rebalancer(budget=0).largest_placeable(sliver_city()) == 600

    def test_not_ready_nodes_do_not_count(self):
        store = cluster(nodes=1)
        store.get_node("n0").ready = False
        assert Rebalancer(budget=0).largest_placeable(store) == 0


class TestRebalance:
    def test_two_moves_buy_back_a_whole_node(self):
        store = sliver_city()
        rebalancer = Rebalancer(budget=10)
        assert rebalancer.rebalance(store) == 2
        assert rebalancer.largest_placeable(store) == 1000

    def test_the_walk_terminates_without_ping_pong(self):
        store = sliver_city()
        rebalancer = Rebalancer(budget=100)
        spent = rebalancer.rebalance(store)
        assert spent < 5
        seen = Counter((move.task, move.source, move.target) for move in rebalancer.moves)
        assert all(count == 1 for count in seen.values())

    def test_the_budget_is_respected(self):
        store = sliver_city()
        rebalancer = Rebalancer(budget=1)
        assert rebalancer.rebalance(store) == 1

    def test_a_consolidated_cluster_needs_no_moves(self):
        store = cluster()
        packed = Task(spec=TaskSpec(name="t", needs=Resources(cpu=900, memory=900)))
        packed.bound_to("n0")
        store.add_task(packed)
        assert Rebalancer(budget=10).rebalance(store) == 0

    def test_moves_go_uphill_only(self):
        store = cluster(nodes=2)
        heavy = Task(spec=TaskSpec(name="heavy", needs=Resources(cpu=600, memory=600)))
        heavy.bound_to("n0")
        store.add_task(heavy)
        light = Task(spec=TaskSpec(name="light", needs=Resources(cpu=100, memory=100)))
        light.bound_to("n1")
        store.add_task(light)
        rebalancer = Rebalancer(budget=10)
        rebalancer.rebalance(store)
        assert store.get_task("light").node == "n0"
        assert store.get_task("heavy").node == "n0"
