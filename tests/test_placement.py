from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.placement import Engine
from fleet.store import Store


def one_slot() -> tuple[Store, Engine]:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    return store, Engine()


def task(name: str, priority: int, cpu: int = 800) -> Task:
    return Task(
        spec=TaskSpec(
            name=name, needs=Resources(cpu=cpu, memory=cpu), priority=priority
        )
    )


class TestPlainPlacement:
    def test_a_fitting_task_binds_and_leaves_the_queue(self):
        store, engine = one_slot()
        engine.submit(store, task("t", priority=100))
        placed, benched = engine.one_pass(store, now=0)
        assert placed == 1 and benched == 0
        assert store.get_task("t").phase == "Bound"
        assert "t" not in engine.queue.waiting

    def test_an_unfitting_task_benches_with_a_reason(self):
        store, engine = one_slot()
        engine.submit(store, task("big", priority=100, cpu=5000))
        placed, benched = engine.one_pass(store, now=0)
        assert placed == 0 and benched == 1
        assert "bench" in engine.journal.story("big")


class TestTreatyPreemption:
    def test_critical_displaces_batch(self):
        store, engine = one_slot()
        engine.submit(store, task("batchling", priority=10))
        engine.one_pass(store, now=0)
        engine.submit(store, task("crit", priority=1500))
        engine.one_pass(store, now=1)
        assert store.get_task("crit").phase == "Bound"
        assert store.get_task("batchling").phase == "Pending"
        assert engine.displaced == 1

    def test_batch_never_displaces_even_a_scavenger(self):
        store, engine = one_slot()
        engine.submit(store, task("scav", priority=0))
        engine.one_pass(store, now=0)
        engine.submit(store, task("batchling", priority=10))
        engine.one_pass(store, now=1)
        assert store.get_task("scav").phase == "Bound"
        assert store.get_task("batchling").phase == "Pending"

    def test_nothing_displaces_system(self):
        store, engine = one_slot()
        engine.submit(store, task("sys", priority=10000))
        engine.one_pass(store, now=0)
        engine.submit(store, task("crit", priority=1500))
        engine.one_pass(store, now=1)
        assert store.get_task("sys").phase == "Bound"
        assert store.get_task("crit").phase == "Pending"

    def test_the_displaced_task_returns_when_room_opens(self):
        store, engine = one_slot()
        engine.submit(store, task("batchling", priority=10))
        engine.one_pass(store, now=0)
        engine.submit(store, task("crit", priority=1500))
        engine.one_pass(store, now=1)
        done = store.get_task("crit")
        generation = done.generation
        done.phase = "Succeeded"
        done.node = None
        store.update_task(done, read_generation=generation)
        for now in range(2, 12):
            engine.one_pass(store, now=now)
        assert store.get_task("batchling").phase == "Bound"

    def test_every_decision_reaches_the_journal(self):
        store, engine = one_slot()
        engine.submit(store, task("batchling", priority=10))
        engine.one_pass(store, now=0)
        engine.submit(store, task("crit", priority=1500))
        engine.one_pass(store, now=1)
        story = engine.journal.story("batchling")
        assert "bind" in story and "displace" in story
