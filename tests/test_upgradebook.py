from __future__ import annotations

from fleet.api import Fleet
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.skewpolicy import SkewGate
from fleet.upgradebook import UpgradeBook
from fleet.verify import violations


def ready_fleet() -> tuple[Fleet, SkewGate]:
    fleet = Fleet()
    gate = SkewGate(control_plane="1.28")
    for number in range(3):
        name = f"n{number}"
        fleet.store.add_node(
            Node(name=name, capacity=Resources(cpu=1000, memory=1000))
        )
        gate.admit_node(name, "1.28")
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
    return fleet, gate


class TestUpgradeBook:
    def test_a_clean_upgrade_walks_every_step(self):
        fleet, gate = ready_fleet()
        record = UpgradeBook().run(
            fleet, gate, "oncall", "1.29", node_versions_after="1.29"
        )
        assert record.succeeded(), record.steps
        assert gate.control_plane == "1.29"
        assert all(name.endswith("-replacement") for name in fleet.store.nodes)
        assert violations(fleet.store) == []

    def test_the_record_reads_in_order(self):
        fleet, gate = ready_fleet()
        record = UpgradeBook().run(
            fleet, gate, "oncall", "1.29", node_versions_after="1.29"
        )
        assert record.steps[0].endswith(": go")
        assert record.steps[1] == "control plane at 1.29"
        assert record.steps[2] == "3 nodes refreshed"
        assert "promises hold at 1.29" in record.steps[3]

    def test_a_skew_violation_stops_at_preflight(self):
        fleet, gate = ready_fleet()
        gate.node_versions["n0"] = "1.26"
        record = UpgradeBook().run(
            fleet, gate, "oncall", "1.29", node_versions_after="1.29"
        )
        assert record.stopped_at == "preflight"
        assert gate.control_plane == "1.28"
        assert "n0" in fleet.store.nodes

    def test_the_gate_tracks_the_refreshed_nodes(self):
        fleet, gate = ready_fleet()
        UpgradeBook().run(fleet, gate, "oncall", "1.29", node_versions_after="1.29")
        assert set(gate.node_versions) == set(fleet.store.nodes)
        assert set(gate.node_versions.values()) == {"1.29"}
