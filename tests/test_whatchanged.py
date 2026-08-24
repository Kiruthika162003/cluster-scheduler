from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store
from fleet.whatchanged import what_changed


def task(name: str) -> Task:
    return Task(spec=TaskSpec(name=name, needs=Resources(cpu=1, memory=1)))


class TestWhatChanged:
    def test_a_quiet_window_says_so(self):
        store = Store()
        store.add_task(task("a"))
        cursor = len(store.events)
        window = what_changed(store, cursor)
        assert window.sentence() == f"nothing changed since {cursor}"

    def test_a_creation_is_created(self):
        store = Store()
        cursor = len(store.events)
        store.add_task(task("a"))
        window = what_changed(store, cursor)
        assert window.sentence() == "created task/a"

    def test_updates_collapse_to_one_change_with_touches(self):
        store = Store()
        store.add_task(task("a"))
        cursor = len(store.events)
        held = store.get_task("a")
        held.phase = "Bound"
        store.update_task(held, read_generation=1)
        held.phase = "Running"
        store.update_task(held, read_generation=2)
        window = what_changed(store, cursor)
        assert window.changes[0].net == "updated"
        assert window.changes[0].touches == 2

    def test_add_then_remove_reports_churn_not_silence(self):
        store = Store()
        cursor = len(store.events)
        store.add_task(task("flapper"))
        store.remove_task("flapper")
        window = what_changed(store, cursor)
        assert window.changes == []
        assert window.churned == ["task/flapper"]
        assert "churned task/flapper" in window.sentence()

    def test_created_then_updated_is_still_created(self):
        store = Store()
        cursor = len(store.events)
        store.add_task(task("a"))
        held = store.get_task("a")
        held.phase = "Bound"
        store.update_task(held, read_generation=1)
        window = what_changed(store, cursor)
        assert window.changes[0].net == "created"
        assert window.changes[0].touches == 2

    def test_nodes_and_tasks_are_distinguished(self):
        store = Store()
        cursor = len(store.events)
        store.add_node(Node(name="n0", capacity=Resources(cpu=1, memory=1)))
        store.add_task(task("a"))
        window = what_changed(store, cursor)
        kinds = {change.kind for change in window.changes}
        assert kinds == {"node", "task"}

    def test_the_window_respects_its_cursor(self):
        store = Store()
        store.add_task(task("old"))
        cursor = len(store.events)
        store.add_task(task("new"))
        window = what_changed(store, cursor)
        names = [change.name for change in window.changes]
        assert names == ["new"]
