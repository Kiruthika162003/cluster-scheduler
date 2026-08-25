from __future__ import annotations

from fleet.objects import Node, Resources
from fleet.quarantine import (
    PROBATION,
    QUARANTINE_TAINT,
    Warden,
)
from fleet.store import Store


def cluster() -> Store:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    return store


class TestTheThreshold:
    def test_one_deploys_crashes_stay_the_tasks_fault(self):
        store = cluster()
        warden = Warden()
        for number in range(5):
            outcome = warden.task_died(
                store, "n0", f"web-{number}", "web", now=number
            )
        assert outcome is None
        assert warden.quarantined() == []

    def test_cross_deploy_kills_convict_the_node(self):
        store = cluster()
        warden = Warden()
        warden.task_died(store, "n0", "web-0", "web", now=0)
        warden.task_died(store, "n0", "api-0", "api", now=1)
        outcome = warden.task_died(store, "n0", "db-0", "db", now=2)
        assert outcome == "quarantined"
        node = store.get_node("n0")
        assert not node.schedulable
        assert any(t.key == QUARANTINE_TAINT for t in node.taints)

    def test_old_kills_roll_out_of_the_window(self):
        store = cluster()
        warden = Warden()
        warden.task_died(store, "n0", "web-0", "web", now=0)
        warden.task_died(store, "n0", "api-0", "api", now=1)
        outcome = warden.task_died(store, "n0", "db-0", "db", now=40)
        assert outcome is None


class TestProbation:
    def convict(self, store: Store, warden: Warden) -> None:
        warden.task_died(store, "n0", "web-0", "web", now=0)
        warden.task_died(store, "n0", "api-0", "api", now=1)
        warden.task_died(store, "n0", "db-0", "db", now=2)

    def test_a_clean_probation_earns_release(self):
        store = cluster()
        warden = Warden()
        self.convict(store, warden)
        assert warden.patrol(store, now=2 + PROBATION - 1) == []
        assert warden.patrol(store, now=2 + PROBATION) == ["n0"]
        node = store.get_node("n0")
        assert node.schedulable
        assert not any(t.key == QUARANTINE_TAINT for t in node.taints)

    def test_a_kill_inside_probation_doubles_the_clock(self):
        store = cluster()
        warden = Warden()
        self.convict(store, warden)
        outcome = warden.task_died(store, "n0", "web-1", "web", now=10)
        assert outcome == "probation restarted"
        assert warden.patrol(store, now=10 + PROBATION) == []
        assert warden.patrol(store, now=10 + 2 * PROBATION) == ["n0"]

    def test_the_clock_has_a_ceiling(self):
        store = cluster()
        warden = Warden()
        self.convict(store, warden)
        for strike in range(6):
            warden.task_died(store, "n0", f"w{strike}", "web", now=10 + strike)
        assert warden.records["n0"].probation == 400

    def test_release_wipes_the_record(self):
        store = cluster()
        warden = Warden()
        self.convict(store, warden)
        warden.patrol(store, now=2 + PROBATION)
        outcome = warden.task_died(store, "n0", "web-9", "web", now=100)
        assert outcome is None


class TestTheLedger:
    def test_the_journal_proves_the_again(self):
        store = cluster()
        warden = Warden()
        warden.task_died(store, "n0", "web-0", "web", now=0)
        warden.task_died(store, "n0", "api-0", "api", now=1)
        warden.task_died(store, "n0", "db-0", "db", now=2)
        warden.patrol(store, now=2 + PROBATION)
        page = warden.report()
        assert "n0 quarantined: killed web-0, api-0, db-0 across 3 deploys" in (
            page
        )
        assert "released after clean probation (stint 1)" in page
