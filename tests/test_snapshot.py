from __future__ import annotations

import json

from fleet.control.deploy import DeploySpec
from fleet.objects import Node, Resources, Taint, TaskSpec
from fleet.sim.cluster import Script, Sim
from fleet.snapshot import dump, restore
from fleet.store import Store


def busy_sim() -> Sim:
    sim = Sim(script=Script(silences={"n1": (3, 8)}))
    sim.add_nodes(3)
    sim.deploys.append(
        DeploySpec(
            name="web",
            replicas=5,
            template=TaskSpec(name="tpl", needs=Resources(cpu=200, memory=200)),
        )
    )
    sim.run(10)
    return sim


class TestRoundTrip:
    def test_dump_restore_dump_is_a_fixed_point(self):
        sim = busy_sim()
        data = dump(sim.store)
        assert dump(restore(data)) == data

    def test_the_snapshot_survives_json(self):
        sim = busy_sim()
        data = json.loads(json.dumps(dump(sim.store)))
        back = restore(data)
        assert len(back.tasks) == len(sim.store.tasks)

    def test_generations_and_restarts_survive(self):
        sim = busy_sim()
        back = restore(dump(sim.store))
        for name, task in sim.store.tasks.items():
            assert back.tasks[name].generation == task.generation
            assert back.tasks[name].restarts == task.restarts

    def test_taints_and_flags_survive(self):
        store = Store()
        node = Node(
            name="gpu-0",
            capacity=Resources(cpu=1000, memory=1000),
            labels={"pool": "gpu"},
            taints=(Taint(key="pool-gpu", effect="NoSchedule"),),
        )
        node.schedulable = False
        node.ready = False
        store.nodes["gpu-0"] = node
        back = restore(dump(store))
        held = back.nodes["gpu-0"]
        assert held.taints[0].key == "pool-gpu"
        assert not held.schedulable and not held.ready

    def test_the_event_log_restarts_empty_by_design(self):
        sim = busy_sim()
        back = restore(dump(sim.store))
        assert back.events == []
        assert sim.store.events != []


class TestContinuation:
    def test_a_restored_cluster_continues_identically(self):
        one = busy_sim()
        data = dump(one.store)
        one.run(10)
        two = Sim(script=Script(silences={"n1": (3, 8)}))
        two.store = restore(data)
        two.deploys.append(one.deploys[0])
        two.now = 10
        two.monitor.marked_not_ready = one.monitor.marked_not_ready
        for name in two.store.nodes:
            two.monitor.beat(two.store, name, 10)
        two.run(10)
        mine = {t.spec.name: (t.phase, t.node) for t in one.store.tasks.values()}
        theirs = {t.spec.name: (t.phase, t.node) for t in two.store.tasks.values()}
        assert mine == theirs
