from __future__ import annotations

from fleet.api import Fleet
from fleet.canaryrefresh import CanaryRefresh
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.verify import violations


def working_fleet() -> Fleet:
    fleet = Fleet()
    for number in range(3):
        fleet.store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    for number in range(3):
        fleet.submit(
            "setup",
            Task(
                spec=TaskSpec(
                    name=f"w{number}", needs=Resources(cpu=300, memory=300)
                )
            ),
        )
    fleet.step()
    return fleet


class TestCanaryRefresh:
    def test_a_good_build_replaces_the_whole_pool(self):
        fleet = working_fleet()
        refresh = CanaryRefresh()
        told = refresh.refresh(fleet, "oncall", ["n0", "n1", "n2"])
        assert told == "refresh complete"
        assert sorted(fleet.store.nodes) == ["n0-next", "n1-next", "n2-next"]
        assert violations(fleet.store) == []

    def test_a_bad_build_halts_at_first_contact(self):
        fleet = working_fleet()
        refresh = CanaryRefresh()
        told = refresh.refresh(
            fleet, "oncall", ["n0", "n1", "n2"], bad_nodes={"n1-next"}
        )
        assert told == "halted at n1"
        assert refresh.halted_on == "n1-next"
        assert refresh.replaced == ["n0"]
        assert "n1" in fleet.store.nodes
        assert "n2" in fleet.store.nodes

    def test_production_never_touched_the_rejected_node(self):
        fleet = working_fleet()
        refresh = CanaryRefresh()
        refresh.refresh(fleet, "oncall", ["n0"], bad_nodes={"n0-next"})
        assert all(
            task.node != "n0-next"
            for task in fleet.store.tasks.values()
            if task.is_active()
        )

    def test_the_graduated_node_serves_the_moved_tasks(self):
        fleet = working_fleet()
        refresh = CanaryRefresh()
        refresh.refresh(fleet, "oncall", ["n0"])
        fleet.step()
        homes = {task.node for task in fleet.store.active_tasks()}
        assert "n0" not in homes
