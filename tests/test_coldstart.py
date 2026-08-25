from __future__ import annotations

from fleet.coldstart import cold_start, rebuild_engine
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.placement import Engine
from fleet.store import Store


def half_done() -> Store:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    bound = Task(spec=TaskSpec(name="placed", needs=Resources(cpu=100, memory=100)))
    engine = Engine()
    engine.submit(store, bound)
    engine.one_pass(store, now=0)
    engine.submit(
        store,
        Task(
            spec=TaskSpec(
                name="waiting",
                needs=Resources(cpu=100, memory=100),
                priority=500,
                namespace="search",
            )
        ),
    )
    return store


class TestRebuild:
    def test_only_pending_tasks_reenter_the_queue(self):
        store = half_done()
        engine = rebuild_engine(store)
        assert sorted(engine.queue.waiting) == ["waiting"]

    def test_the_queue_entry_keeps_priority_and_namespace(self):
        store = half_done()
        engine = rebuild_engine(store)
        held = engine.queue.waiting["waiting"]
        assert held.priority == 500 and held.namespace == "search"

    def test_the_informer_arrives_synced(self):
        store = half_done()
        _, informer = cold_start(store)
        assert informer.agrees_with(store)

    def test_the_reborn_engine_places_the_backlog(self):
        store = half_done()
        engine, _ = cold_start(store)
        engine.one_pass(store, now=1)
        assert store.get_task("waiting").is_active()
