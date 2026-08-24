from __future__ import annotations

import pytest

from fleet.errors import Conflict, NotFound
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def task(name: str = "t") -> Task:
    return Task(spec=TaskSpec(name=name, needs=Resources(cpu=1, memory=1)))


class TestTasks:
    def test_add_then_get(self):
        store = Store()
        store.add_task(task("a"))
        assert store.get_task("a").spec.name == "a"

    def test_double_add_conflicts(self):
        store = Store()
        store.add_task(task("a"))
        with pytest.raises(Conflict):
            store.add_task(task("a"))

    def test_get_of_nothing_is_not_found(self):
        with pytest.raises(NotFound):
            Store().get_task("ghost")

    def test_update_with_the_read_generation_lands(self):
        store = Store()
        store.add_task(task("a"))
        held = store.get_task("a")
        held.phase = "Bound"
        store.update_task(held, read_generation=1)
        assert store.get_task("a").generation == 2

    def test_a_stale_update_is_refused_and_counted(self):
        store = Store()
        store.add_task(task("a"))
        held = store.get_task("a")
        store.update_task(held, read_generation=1)
        with pytest.raises(Conflict):
            store.update_task(held, read_generation=1)
        assert store.refused == 1

    def test_remove_makes_get_fail(self):
        store = Store()
        store.add_task(task("a"))
        store.remove_task("a")
        with pytest.raises(NotFound):
            store.get_task("a")


class TestNodesAndViews:
    def test_nodes_round_trip(self):
        store = Store()
        store.add_node(Node(name="n1", capacity=Resources(cpu=1, memory=1)))
        assert store.get_node("n1").name == "n1"

    def test_pending_and_active_partition_by_phase(self):
        store = Store()
        store.add_task(task("a"))
        bound = task("b")
        bound.bound_to("n1")
        store.add_task(bound)
        assert [t.spec.name for t in store.pending_tasks()] == ["a"]
        assert [t.spec.name for t in store.active_tasks()] == ["b"]


class TestEvents:
    def test_every_accepted_write_appends_one_event(self):
        store = Store()
        store.add_task(task("a"))
        held = store.get_task("a")
        store.update_task(held, read_generation=1)
        store.remove_task("a")
        assert [e.kind for e in store.events] == [
            "task-added",
            "task-updated",
            "task-removed",
        ]

    def test_a_refused_write_appends_nothing(self):
        store = Store()
        store.add_task(task("a"))
        before = len(store.events)
        held = store.get_task("a")
        store.update_task(held, read_generation=1)
        with pytest.raises(Conflict):
            store.update_task(held, read_generation=1)
        assert len(store.events) == before + 1

    def test_since_replays_from_the_cursor(self):
        store = Store()
        store.add_task(task("a"))
        store.add_task(task("b"))
        assert [e.name for e in store.since(1)] == ["b"]
        assert store.since(2) == []
