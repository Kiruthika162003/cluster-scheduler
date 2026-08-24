from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.balloon import BalloonFleet
from fleet.sched.placement import Engine
from fleet.store import Store


def roomy_store() -> Store:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=2000, memory=2000)))
    return store


class TestBalloonFleet:
    def test_balloons_inflate_where_there_is_room(self):
        store = roomy_store()
        engine = Engine()
        fleet = BalloonFleet(shape=Resources(cpu=500, memory=500), count=2)
        fleet.submit(store, engine)
        engine.one_pass(store, now=0)
        assert fleet.inflated(store) == 2

    def test_balloons_bench_on_a_full_cluster(self):
        store = Store()
        store.add_node(Node(name="n0", capacity=Resources(cpu=400, memory=400)))
        engine = Engine()
        squatter = Task(
            spec=TaskSpec(
                name="squatter", needs=Resources(cpu=400, memory=400), priority=0
            )
        )
        engine.submit(store, squatter)
        engine.one_pass(store, now=0)
        fleet = BalloonFleet(shape=Resources(cpu=400, memory=400), count=1)
        fleet.submit(store, engine)
        engine.one_pass(store, now=1)
        assert fleet.inflated(store) == 0

    def test_anything_above_scavenger_pops_a_balloon(self):
        store = roomy_store()
        engine = Engine()
        fleet = BalloonFleet(shape=Resources(cpu=1000, memory=1000), count=2)
        fleet.submit(store, engine)
        engine.one_pass(store, now=0)
        batchling = Task(
            spec=TaskSpec(
                name="batchling", needs=Resources(cpu=1000, memory=1000), priority=10
            )
        )
        engine.submit(store, batchling)
        engine.one_pass(store, now=1)
        assert store.get_task("batchling").phase == "Pending"
        assert fleet.popped_ever(engine) == 0

    def test_normal_work_pops_balloons_batch_does_not(self):
        store = roomy_store()
        engine = Engine()
        fleet = BalloonFleet(shape=Resources(cpu=1000, memory=1000), count=2)
        fleet.submit(store, engine)
        engine.one_pass(store, now=0)
        worker = Task(
            spec=TaskSpec(
                name="worker", needs=Resources(cpu=1000, memory=1000), priority=100
            )
        )
        engine.submit(store, worker)
        engine.one_pass(store, now=1)
        assert store.get_task("worker").is_active()
        assert fleet.popped_ever(engine) == 1
