from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.failuredomains import DomainAudit
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def labelled_cluster() -> Store:
    store = Store()
    layout = {
        "n0": ("r1", "za"),
        "n1": ("r1", "za"),
        "n2": ("r2", "za"),
        "n3": ("r3", "zb"),
    }
    for name, (rack, zone) in layout.items():
        store.add_node(
            Node(
                name=name,
                capacity=Resources(cpu=1000, memory=1000),
                labels={"rack": rack, "zone": zone},
            )
        )
    return store


def place(store: Store, deploy: str, replica: int, node: str) -> None:
    task = Task(
        spec=TaskSpec(
            name=f"{deploy}-{replica}", needs=Resources(cpu=100, memory=100)
        )
    )
    task.bound_to(node)
    store.add_task(task)


class TestExposures:
    def test_the_stacked_deploy_is_seen_through_its_health(self):
        store = labelled_cluster()
        for replica, node in enumerate(("n0", "n1", "n0")):
            place(store, "web", replica, node)
        audit = DomainAudit(store=store, floors={"web": 2})
        rack_row = next(
            e for e in audit.worst_exposures() if e.level == "rack"
        )
        assert rack_row.domain == "r1"
        assert rack_row.share() == 1.0
        assert audit.verdicts()

    def test_racks_can_pass_while_zones_cannot(self):
        store = labelled_cluster()
        for replica, node in enumerate(("n0", "n2", "n3")):
            place(store, "web", replica, node)
        audit = DomainAudit(store=store, floors={"web": 2})
        failed = audit.verdicts()
        assert len(failed) == 1
        assert failed[0].startswith("web: losing zone za")

    def test_a_two_zone_fleet_cannot_hold_a_floor_of_two(self):
        store = labelled_cluster()
        for replica, node in enumerate(("n0", "n2", "n3")):
            place(store, "web", replica, node)
        relaxed = DomainAudit(store=store, floors={"web": 1})
        assert relaxed.verdicts() == []
        assert relaxed.report() == (
            "every deploy survives its worst single domain"
        )

    def test_zone_concentration_is_its_own_finding(self):
        store = labelled_cluster()
        for replica, node in enumerate(("n0", "n1", "n2")):
            place(store, "web", replica, node)
        audit = DomainAudit(store=store, floors={"web": 1})
        zone_row = next(
            e for e in audit.worst_exposures() if e.level == "zone"
        )
        assert zone_row.domain == "za"
        assert zone_row.share() == 1.0

    def test_unlabelled_nodes_break_the_audit_loudly(self):
        store = labelled_cluster()
        store.add_node(
            Node(name="bare", capacity=Resources(cpu=1000, memory=1000))
        )
        place(store, "web", 0, "bare")
        with pytest.raises(Invalid, match="no rack label"):
            DomainAudit(store=store).worst_exposures()


class TestReport:
    def test_the_report_names_the_floor_breach(self):
        store = labelled_cluster()
        for replica, node in enumerate(("n0", "n1", "n2")):
            place(store, "api", replica, node)
        audit = DomainAudit(store=store, floors={"api": 2})
        page = audit.report()
        assert "api: losing rack r1 kills 2 of 3 (67%)" in page
        assert "leaving 1 against a floor of 2" in page
