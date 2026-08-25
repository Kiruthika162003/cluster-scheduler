from __future__ import annotations

import pytest

from fleet.errors import Conflict, Invalid, NotFound
from fleet.holds import HOLD_TAG, Hold, HoldLedger
from fleet.objects import Node, Resources, Task, TaskSpec


def node() -> Node:
    return Node(name="n0", capacity=Resources(cpu=1000, memory=1000))


def booking(name: str = "launch", cpu: int = 400,
            starts: int = 10, ends: int = 20) -> Hold:
    return Hold(
        name=name,
        node="n0",
        amount=Resources(cpu=cpu, memory=cpu),
        starts=starts,
        ends=ends,
    )


def walk_in(cpu: int, tag: str | None = None) -> Task:
    labels = {HOLD_TAG: tag} if tag else {}
    return Task(
        spec=TaskSpec(
            name="walkin",
            needs=Resources(cpu=cpu, memory=cpu),
            labels=labels,
        )
    )


class TestBooking:
    def test_an_empty_window_is_refused(self):
        with pytest.raises(Invalid):
            HoldLedger().book(booking(starts=20, ends=20), node())

    def test_overlapping_bookings_must_fit_together(self):
        ledger = HoldLedger()
        ledger.book(booking("launch", cpu=600), node())
        with pytest.raises(Conflict, match="oversell"):
            ledger.book(booking("other", cpu=600), node())

    def test_disjoint_windows_may_each_take_the_whole_node(self):
        ledger = HoldLedger()
        ledger.book(booking("week1", cpu=900, starts=0, ends=10), node())
        ledger.book(booking("week2", cpu=900, starts=10, ends=20), node())
        assert len(ledger.holds) == 2

    def test_cancelling_the_unbooked_is_named(self):
        with pytest.raises(NotFound):
            HoldLedger().cancel("ghost")


class TestAdmission:
    def test_untagged_work_may_not_eat_the_hold(self):
        ledger = HoldLedger()
        ledger.book(booking(cpu=400), node())
        ok, why = ledger.admits(walk_in(700), node(), tick=15)
        assert not ok
        assert "400m cpu is held" in why

    def test_untagged_work_fits_beside_the_hold(self):
        ledger = HoldLedger()
        ledger.book(booking(cpu=400), node())
        ok, _ = ledger.admits(walk_in(600), node(), tick=15)
        assert ok

    def test_the_hold_only_binds_inside_the_window(self):
        ledger = HoldLedger()
        ledger.book(booking(cpu=400, starts=10, ends=20), node())
        ok, _ = ledger.admits(walk_in(900), node(), tick=5)
        assert ok

    def test_tagged_work_redeems_its_booking(self):
        ledger = HoldLedger()
        ledger.book(booking(cpu=400), node())
        ok, why = ledger.admits(walk_in(400, tag="launch"), node(), tick=15)
        assert ok
        assert why == "redeeming the hold"

    def test_redeeming_on_the_wrong_node_is_refused(self):
        ledger = HoldLedger()
        ledger.book(booking(cpu=400), node())
        other = Node(name="n1", capacity=Resources(cpu=1000, memory=1000))
        ok, why = ledger.admits(walk_in(400, tag="launch"), other, tick=15)
        assert not ok
        assert "is on n0" in why

    def test_redeeming_outside_the_window_is_refused(self):
        ledger = HoldLedger()
        ledger.book(booking(cpu=400, starts=10, ends=20), node())
        ok, why = ledger.admits(walk_in(400, tag="launch"), node(), tick=25)
        assert not ok
        assert "not active" in why

    def test_a_phantom_reservation_is_refused_by_name(self):
        ledger = HoldLedger()
        ok, why = ledger.admits(walk_in(100, tag="ghost"), node(), tick=0)
        assert not ok
        assert "ghost does not exist" in why


class TestExpiry:
    def test_expiry_returns_the_swept_names(self):
        ledger = HoldLedger()
        ledger.book(booking("old", starts=0, ends=10), node())
        ledger.book(booking("new", starts=15, ends=30), node())
        assert ledger.expire(tick=12) == ["old"]
        assert list(ledger.holds) == ["new"]

    def test_the_report_names_each_state(self):
        ledger = HoldLedger()
        ledger.book(booking("now", starts=10, ends=20), node())
        ledger.book(booking("later", starts=30, ends=40), node())
        page = ledger.report(tick=15)
        assert "now: 400m on n0 [10, 20) active" in page
        assert "later: 400m on n0 [30, 40) upcoming" in page
