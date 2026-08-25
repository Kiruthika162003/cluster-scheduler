from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store
from fleet.subscriptions import subscribe


def task(name: str, **labels: str) -> Task:
    return Task(
        spec=TaskSpec(
            name=name,
            needs=Resources(cpu=1, memory=1),
            labels=tuple(sorted(labels.items())),
        )
    )


class TestFiltering:
    def test_a_kind_subscription_sees_only_its_kind(self):
        store = Store()
        watcher = subscribe("nodes-only", kind_prefix="node")
        store.add_task(task("t"))
        store.add_node(Node(name="n0", capacity=Resources(cpu=1, memory=1)))
        events = watcher.pull(store)
        assert [event.kind for event in events] == ["node-added"]

    def test_a_selector_subscription_sees_matching_tasks(self):
        store = Store()
        watcher = subscribe("web-watch", selector_text="app=web")
        store.add_task(task("web-0", app="web"))
        store.add_task(task("db-0", app="db"))
        events = watcher.pull(store)
        assert [event.name for event in events] == ["web-0"]

    def test_an_unfiltered_subscription_sees_everything(self):
        store = Store()
        watcher = subscribe("all")
        store.add_task(task("t"))
        store.add_node(Node(name="n0", capacity=Resources(cpu=1, memory=1)))
        assert len(watcher.pull(store)) == 2


class TestResume:
    def test_no_gaps_no_repeats_across_pulls(self):
        store = Store()
        watcher = subscribe("all")
        store.add_task(task("a"))
        first = watcher.pull(store)
        store.add_task(task("b"))
        second = watcher.pull(store)
        assert [event.name for event in first] == ["a"]
        assert [event.name for event in second] == ["b"]

    def test_a_restored_cursor_resumes_exactly(self):
        store = Store()
        watcher = subscribe("all")
        store.add_task(task("a"))
        watcher.pull(store)
        saved = watcher.cursor
        store.add_task(task("b"))
        store.add_task(task("c"))
        reborn = subscribe("all")
        reborn.cursor = saved
        events = reborn.pull(store)
        assert [event.name for event in events] == ["b", "c"]

    def test_the_cursor_advances_past_filtered_events(self):
        store = Store()
        watcher = subscribe("web-watch", selector_text="app=web")
        store.add_task(task("db-0", app="db"))
        assert watcher.pull(store) == []
        assert watcher.cursor == len(store.events)

    def test_a_deleted_subject_no_longer_matches(self):
        store = Store()
        watcher = subscribe("web-watch", selector_text="app=web")
        store.add_task(task("web-0", app="web"))
        store.remove_task("web-0")
        events = watcher.pull(store)
        assert events == []
