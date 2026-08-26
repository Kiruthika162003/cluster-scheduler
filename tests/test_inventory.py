from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.inventory import LedgerEntry, reconcile, report
from fleet.objects import Node, Resources
from fleet.store import Store


def ledger() -> list[LedgerEntry]:
    return [
        LedgerEntry(name=f"n{number}", cpu=1000, memory=1000)
        for number in range(4)
    ]


def cluster(names: tuple[str, ...]) -> Store:
    store = Store()
    for name in names:
        store.add_node(
            Node(name=name, capacity=Resources(cpu=1000, memory=1000))
        )
    return store


class TestReconciling:
    def test_a_clean_fleet_matches_everywhere(self):
        result = reconcile(ledger(), cluster(("n0", "n1", "n2", "n3")))
        assert result.clean()
        assert result.matched == 4

    def test_the_billed_but_absent_are_dark(self):
        result = reconcile(ledger(), cluster(("n0", "n1")))
        assert result.dark == ["n2", "n3"]

    def test_the_unapproved_are_ghosts(self):
        result = reconcile(ledger(), cluster(("n0", "n1", "n2", "n3", "n9")))
        assert result.ghosts == ["n9"]

    def test_the_quiet_hardware_swap_is_caught(self):
        store = cluster(("n0", "n1", "n2"))
        store.add_node(
            Node(name="n3", capacity=Resources(cpu=4000, memory=1000))
        )
        result = reconcile(ledger(), store)
        assert result.swapped == [
            "n3: ledger says 1000m/1000, metal says 4000m/1000"
        ]
        assert result.matched == 3

    def test_a_double_entry_ledger_is_refused(self):
        doubled = [*ledger(), LedgerEntry(name="n0", cpu=1, memory=1)]
        with pytest.raises(Invalid):
            reconcile(doubled, cluster(("n0",)))


class TestTheScore:
    def test_drift_is_the_troubled_share_of_the_ledger(self):
        result = reconcile(ledger(), cluster(("n0", "n1", "n9")))
        assert result.drift_score(len(ledger())) == 0.75

    def test_an_empty_ledger_cannot_drift(self):
        result = reconcile(ledger(), cluster(("n0",)))
        with pytest.raises(Invalid):
            result.drift_score(0)

    def test_the_report_attaches_the_evidence(self):
        store = cluster(("n0", "n1", "n9"))
        page = report(ledger(), store)
        assert "drift 75.0%: 2 matched" in page
        assert "dark: n2 is billed but absent" in page
        assert "ghost: n9 works here but nobody approved it" in page

    def test_the_clean_report_is_one_line(self):
        page = report(ledger(), cluster(("n0", "n1", "n2", "n3")))
        assert page == "clean: all 4 nodes match the ledger"
