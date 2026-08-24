from __future__ import annotations

from fleet.control.budget import Budget, Guard
from fleet.control.deploy import DeploySpec
from fleet.objects import Node, Resources, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.filters import is_ready
from fleet.sim.cluster import Sim
from fleet.store import Store
from fleet.upgradewalk import Walk


def webbed_sim(replicas: int = 8) -> Sim:
    sim = Sim()
    sim.add_nodes(4)
    sim.deploys.append(
        DeploySpec(
            name="web",
            replicas=replicas,
            template=TaskSpec(
                name="tpl",
                needs=Resources(cpu=400, memory=400),
                labels=(("app", "web"),),
            ),
        )
    )
    sim.run(5)
    return sim


def web_guard(floor: int) -> Guard:
    return Guard(
        budgets=[
            Budget(
                name="floor",
                selector_key="app",
                selector_value="web",
                min_available=floor,
            )
        ]
    )


class TestCordon:
    def test_a_cordoned_node_refuses_new_tasks(self):
        node = Node(name="n", capacity=Resources(cpu=1000, memory=1000))
        node.schedulable = False
        from fleet.objects import Task

        task = Task(spec=TaskSpec(name="t", needs=Resources(cpu=1, memory=1)))
        assert is_ready(task, node, []) == "node cordoned"

    def test_a_cordoned_node_still_serves(self):
        sim = webbed_sim()
        sim.store.get_node("n0").schedulable = False
        assert sim.serving_count() == 8

    def test_the_scheduler_avoids_the_cordon(self):
        store = Store()
        store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
        store.get_node("n0").schedulable = False
        store.add_node(Node(name="n1", capacity=Resources(cpu=1000, memory=1000)))
        from fleet.objects import Task

        task = Task(spec=TaskSpec(name="t", needs=Resources(cpu=100, memory=100)))
        store.add_task(task)
        Scheduler().schedule(store, task)
        assert task.node == "n1"


class TestWalk:
    def test_every_node_gets_patched(self):
        sim = webbed_sim()
        walk = Walk(guard=web_guard(6))
        walk.upgrade(sim, ["n0", "n1", "n2", "n3"])
        assert walk.patched == ["n0", "n1", "n2", "n3"]

    def test_the_cluster_ends_whole_and_uncordoned(self):
        sim = webbed_sim()
        walk = Walk(guard=web_guard(6))
        walk.upgrade(sim, ["n0", "n1", "n2", "n3"])
        assert sim.serving_count() == 8
        assert all(node.schedulable for node in sim.store.nodes.values())

    def test_the_floor_respects_the_budget(self):
        sim = webbed_sim()
        walk = Walk(guard=web_guard(6))
        walk.upgrade(sim, ["n0", "n1", "n2", "n3"])
        assert walk.floor_seen == 6

    def test_the_surge_node_leaves_no_trace(self):
        sim = webbed_sim()
        walk = Walk(guard=web_guard(6))
        walk.upgrade(
            sim,
            ["n0", "n1", "n2", "n3"],
            surge=Resources(cpu=1000, memory=1000),
        )
        assert "surge" not in sim.store.nodes
        assert walk.floor_seen == 8
