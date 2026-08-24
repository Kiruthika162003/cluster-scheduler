from __future__ import annotations

from collections import Counter

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.filters import EVERY_FILTER
from fleet.sched.scorers import binpack
from fleet.sched.topology import SpreadRule, skew_now, spread_filter, tallies, zone_map
from fleet.store import Store


def zoned_store() -> Store:
    store = Store()
    for number, zone in enumerate(["a", "a", "b", "b", "c", "c"]):
        store.add_node(
            Node(
                name=f"n{number}",
                capacity=Resources(cpu=1000, memory=1000),
                labels={"zone": zone},
            )
        )
    return store


def web(name: str) -> Task:
    return Task(
        spec=TaskSpec(
            name=name, needs=Resources(cpu=100, memory=100), labels=(("app", "web"),)
        )
    )


def rule() -> SpreadRule:
    return SpreadRule(label_key="app", label_value="web", max_skew=1)


class TestZoneMap:
    def test_only_zoned_nodes_appear(self):
        nodes = [
            Node(name="z", capacity=Resources.none(), labels={"zone": "a"}),
            Node(name="bare", capacity=Resources.none()),
        ]
        assert zone_map(nodes) == {"z": "a"}

    def test_tallies_count_only_matching_tasks(self):
        store = zoned_store()
        zones = zone_map(list(store.nodes.values()))
        task = web("w0")
        task.bound_to("n0")
        other = Task(spec=TaskSpec(name="x", needs=Resources.none()))
        other.bound_to("n2")
        counts = tallies(rule(), zones, [task, other])
        assert counts == {"a": 1, "b": 0, "c": 0}


class TestSpreadFilter:
    def test_the_cap_refuses_the_skewing_zone(self):
        store = zoned_store()
        zones = zone_map(list(store.nodes.values()))
        placed = web("w0")
        placed.bound_to("n0")
        check = spread_filter(rule(), zones)
        refusal = check(web("w1"), store.get_node("n1"), [placed])
        assert refusal is not None and "skew" in refusal

    def test_an_empty_zone_is_welcome(self):
        store = zoned_store()
        zones = zone_map(list(store.nodes.values()))
        placed = web("w0")
        placed.bound_to("n0")
        check = spread_filter(rule(), zones)
        assert check(web("w1"), store.get_node("n2"), [placed]) is None

    def test_unmatched_tasks_pass_untouched(self):
        store = zoned_store()
        zones = zone_map(list(store.nodes.values()))
        check = spread_filter(rule(), zones)
        loner = Task(spec=TaskSpec(name="x", needs=Resources.none()))
        assert check(loner, store.get_node("n0"), []) is None

    def test_a_zoneless_node_is_refused_for_matching_tasks(self):
        store = zoned_store()
        store.add_node(Node(name="bare", capacity=Resources(cpu=1000, memory=1000)))
        zones = zone_map(list(store.nodes.values()))
        check = spread_filter(rule(), zones)
        assert check(web("w0"), store.get_node("bare"), []) == "node has no zone"


class TestSpreadAgainstPacking:
    def test_binpack_alone_stacks_one_node(self):
        store = zoned_store()
        for number in range(6):
            store.add_task(web(f"w{number}"))
        Scheduler(scorers=(binpack,)).schedule_pending(store)
        assert len({task.node for task in store.active_tasks()}) == 1

    def test_the_skew_cap_forces_even_zones(self):
        store = zoned_store()
        zones = zone_map(list(store.nodes.values()))
        guard = spread_filter(rule(), zones)
        scheduler = Scheduler(scorers=(binpack,), filters=(*EVERY_FILTER, guard))
        for number in range(7):
            store.add_task(web(f"w{number}"))
        placed, stuck = scheduler.schedule_pending(store)
        assert placed == 7 and stuck == 0
        by_zone = Counter(zones[task.node] for task in store.active_tasks())
        assert sorted(by_zone.values()) == [2, 2, 3]
        assert skew_now(rule(), zones, store.active_tasks()) == 1

    def test_losing_the_fullest_zone_loses_a_bounded_slice(self):
        store = zoned_store()
        zones = zone_map(list(store.nodes.values()))
        guard = spread_filter(rule(), zones)
        scheduler = Scheduler(scorers=(binpack,), filters=(*EVERY_FILTER, guard))
        for number in range(7):
            store.add_task(web(f"w{number}"))
        scheduler.schedule_pending(store)
        by_zone = Counter(zones[task.node] for task in store.active_tasks())
        assert max(by_zone.values()) == 3
