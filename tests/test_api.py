from __future__ import annotations

import pytest

from fleet.api import Fleet
from fleet.control.budget import Budget
from fleet.control.deploy import DeploySpec
from fleet.errors import NotFound
from fleet.objects import Node, Resources, Task, TaskSpec


def fleet_of(nodes: int = 2) -> Fleet:
    fleet = Fleet()
    for number in range(nodes):
        fleet.store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    return fleet


def task(name: str, cpu: int = 100, **kw) -> Task:
    return Task(
        spec=TaskSpec(name=name, needs=Resources(cpu=cpu, memory=cpu), **kw)
    )


class TestVerbs:
    def test_submit_queues_and_journals(self):
        fleet = fleet_of()
        fleet.submit("kiruthika", task("t"))
        fleet.step()
        assert fleet.store.get_task("t").is_active()
        assert "submit t" in fleet.journal.story("t")

    def test_delete_forgets_the_queue_entry_too(self):
        fleet = fleet_of()
        fleet.submit("kiruthika", task("t"))
        fleet.delete("kiruthika", "t")
        assert "t" not in fleet.store.tasks
        assert "t" not in fleet.engine.queue.waiting

    def test_deleting_a_ghost_is_not_found(self):
        with pytest.raises(NotFound):
            fleet_of().delete("kiruthika", "ghost")

    def test_apply_and_scale_share_one_spelling(self):
        fleet = fleet_of()
        spec = DeploySpec(
            name="web",
            replicas=2,
            template=TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100)),
        )
        fleet.apply_deploy("kiruthika", spec)
        fleet.scale("kiruthika", "web", 4)
        assert len(fleet.store.tasks) == 4
        assert "replicas 4" in fleet.journal.story("web")

    def test_scaling_an_unapplied_deploy_is_not_found(self):
        with pytest.raises(NotFound):
            fleet_of().scale("kiruthika", "ghost", 3)


class TestNodeVerbs:
    def test_cordon_stops_placement_and_journals(self):
        fleet = fleet_of(nodes=1)
        fleet.cordon("kiruthika", "n0")
        fleet.submit("kiruthika", task("t"))
        placed, benched = fleet.step()
        assert placed == 0 and benched == 1
        assert "cordon n0" in fleet.journal.story("n0")

    def test_uncordon_reopens_the_node(self):
        fleet = fleet_of(nodes=1)
        fleet.cordon("kiruthika", "n0")
        fleet.uncordon("kiruthika", "n0")
        fleet.submit("kiruthika", task("t"))
        placed, _ = fleet.step()
        assert placed == 1

    def test_drain_cordons_evicts_and_requeues(self):
        fleet = fleet_of()
        fleet.submit("kiruthika", task("t"))
        fleet.step()
        home = fleet.store.get_task("t").node
        evicted, refused = fleet.drain("kiruthika", home)
        assert evicted == ["t"] and refused == []
        fleet.step()
        assert fleet.store.get_task("t").node != home

    def test_a_budget_shapes_the_drain(self):
        fleet = fleet_of(nodes=1)
        fleet.guard.budgets.append(
            Budget(
                name="floor",
                selector_key="app",
                selector_value="web",
                min_available=1,
            )
        )
        fleet.submit("kiruthika", task("w", labels=(("app", "web"),)))
        fleet.step()
        evicted, refused = fleet.drain("kiruthika", "n0")
        assert evicted == [] and refused == ["w"]
