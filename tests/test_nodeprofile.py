from __future__ import annotations

from fleet.nodeprofile import (
    SPEED_LABEL,
    WorkClock,
    profiled_node,
    speed_of,
    speed_scorer,
)
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


class TestProfiles:
    def test_a_profiled_node_carries_its_speed(self):
        node = profiled_node("n", cpu=1000, speed=3)
        assert node.labels[SPEED_LABEL] == "3"
        assert speed_of(node) == 3

    def test_an_unlabelled_node_defaults_to_speed_one(self):
        bare = Node(name="n", capacity=Resources(cpu=1, memory=1))
        assert speed_of(bare) == 1

    def test_the_scorer_prefers_faster_iron(self):
        fast = profiled_node("fast", cpu=1000, speed=3)
        slow = profiled_node("slow", cpu=1000, speed=1)
        score = speed_scorer()
        task = Task(spec=TaskSpec(name="t", needs=Resources(cpu=1, memory=1)))
        assert score(task, fast, []) > score(task, slow, [])


class TestWorkClock:
    def clocked_store(self) -> Store:
        store = Store()
        store.nodes["fast"] = profiled_node("fast", cpu=1000, speed=3)
        store.nodes["slow"] = profiled_node("slow", cpu=1000, speed=1)
        for name, home in (("a", "fast"), ("b", "slow")):
            task = Task(spec=TaskSpec(name=name, needs=Resources(cpu=100, memory=100)))
            task.bound_to(home)
            store.tasks[name] = task
        return store

    def test_finish_ticks_divide_by_speed_rounding_up(self):
        clock = WorkClock(work_units=4)
        clock.measure(self.clocked_store())
        assert clock.finish_ticks == {"a": 2, "b": 4}

    def test_the_spread_is_the_finish_gap(self):
        clock = WorkClock(work_units=4)
        clock.measure(self.clocked_store())
        assert clock.spread() == 2

    def test_an_empty_clock_has_no_spread(self):
        assert WorkClock(work_units=4).spread() == 0
