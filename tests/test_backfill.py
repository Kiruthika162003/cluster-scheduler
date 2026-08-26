from __future__ import annotations

import pytest

from fleet.backfill import Backfiller
from fleet.errors import Invalid
from fleet.holds import Hold, HoldLedger
from fleet.objects import Node, Resources


def rig() -> Backfiller:
    ledger = HoldLedger()
    node = Node(name="n0", capacity=Resources(cpu=1000, memory=1000))
    ledger.book(
        Hold(
            name="launch",
            node="n0",
            amount=Resources(cpu=600, memory=600),
            starts=50,
            ends=80,
        ),
        node,
    )
    return Backfiller(ledger=ledger)


class TestBorrowing:
    def test_scavenger_work_borrows_idle_held_cpu(self):
        filler = rig()
        loan = filler.borrow("crunch", cpu=400, needs_ticks=30, node="n0", now=0)
        assert loan is not None
        assert loan.due_at == 50

    def test_work_that_cannot_finish_is_refused(self):
        filler = rig()
        assert (
            filler.borrow("slow", cpu=100, needs_ticks=60, node="n0", now=0)
            is None
        )

    def test_loans_never_oversubscribe_the_hold(self):
        filler = rig()
        filler.borrow("a", cpu=400, needs_ticks=10, node="n0", now=0)
        assert (
            filler.borrow("b", cpu=300, needs_ticks=10, node="n0", now=0)
            is None
        )
        assert (
            filler.borrow("c", cpu=200, needs_ticks=10, node="n0", now=0)
            is not None
        )

    def test_an_active_window_lends_nothing(self):
        filler = rig()
        assert (
            filler.borrow("late", cpu=100, needs_ticks=5, node="n0", now=55)
            is None
        )

    def test_double_borrowing_is_refused(self):
        filler = rig()
        filler.borrow("a", cpu=100, needs_ticks=10, node="n0", now=0)
        with pytest.raises(Invalid):
            filler.borrow("a", cpu=100, needs_ticks=10, node="n0", now=1)


class TestTheWindowEdge:
    def test_the_sweep_evicts_exactly_the_due(self):
        filler = rig()
        filler.borrow("crunch", cpu=400, needs_ticks=45, node="n0", now=0)
        assert filler.sweep(now=49) == []
        assert filler.sweep(now=50) == ["crunch"]
        assert filler.evictions == 1

    def test_finishing_early_beats_the_sweep(self):
        filler = rig()
        filler.borrow("crunch", cpu=400, needs_ticks=30, node="n0", now=0)
        filler.finish("crunch", now=30)
        assert filler.sweep(now=50) == []
        assert filler.finished == 1

    def test_finishing_the_loanless_is_named(self):
        with pytest.raises(Invalid):
            rig().finish("ghost", now=10)


class TestTheReceipt:
    def test_utilisation_bought_and_evictions_paid(self):
        filler = rig()
        filler.borrow("a", cpu=400, needs_ticks=30, node="n0", now=0)
        filler.finish("a", now=30)
        filler.borrow("b", cpu=600, needs_ticks=15, node="n0", now=30)
        filler.sweep(now=50)
        assert filler.lent_ticks == 400 * 30 + 600 * 20
        assert filler.receipt() == "24000 cpu-ticks lent, 1 finished, 1 evicted"
