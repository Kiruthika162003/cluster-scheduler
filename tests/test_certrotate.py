from __future__ import annotations

import pytest

from fleet.certrotate import OVERLAP, Rotator
from fleet.errors import Invalid, NotFound


def pinned_world() -> Rotator:
    rotator = Rotator()
    first = rotator.issue(now=0)
    rotator.pin("web", first.serial, now=0)
    rotator.pin("api", first.serial, now=0)
    return rotator


class TestRotation:
    def test_both_truths_hold_inside_the_overlap(self):
        rotator = pinned_world()
        fresh = rotator.rotate(now=50)
        rotator.pin("api", fresh.serial, now=51)
        ok_old, _ = rotator.verify("web", now=60)
        ok_new, _ = rotator.verify("api", now=60)
        assert ok_old and ok_new

    def test_the_old_truth_dies_when_the_overlap_ends(self):
        rotator = pinned_world()
        rotator.rotate(now=50)
        ok, why = rotator.verify("web", now=50 + OVERLAP)
        assert not ok
        assert "expired at 70" in why

    def test_current_is_the_newest_valid(self):
        rotator = pinned_world()
        fresh = rotator.rotate(now=50)
        assert rotator.current(60).serial == fresh.serial

    def test_pinning_to_the_expired_is_refused(self):
        rotator = pinned_world()
        rotator.rotate(now=50)
        with pytest.raises(Invalid):
            rotator.pin("late", 1, now=50 + OVERLAP)


class TestRevocation:
    def test_revocation_ignores_the_overlap(self):
        rotator = pinned_world()
        rotator.rotate(now=50)
        rotator.revoke(1)
        ok, why = rotator.verify("web", now=55)
        assert not ok
        assert "revoked" in why

    def test_revoking_the_unknown_is_named(self):
        with pytest.raises(NotFound):
            Rotator().revoke(99)


class TestLaggards:
    def test_laggards_are_ordered_by_time_left(self):
        rotator = pinned_world()
        rotator.rotate(now=50)
        rows = rotator.laggards(now=55)
        assert rows == [("api", 15), ("web", 15)]

    def test_repinned_clients_leave_the_list(self):
        rotator = pinned_world()
        fresh = rotator.rotate(now=50)
        rotator.pin("web", fresh.serial, now=51)
        assert rotator.laggards(now=55) == [("api", 15)]

    def test_the_broken_read_zero(self):
        rotator = pinned_world()
        rotator.rotate(now=50)
        rows = rotator.laggards(now=50 + OVERLAP + 5)
        assert rows == [("api", 0), ("web", 0)]

    def test_the_report_is_an_actionable_page(self):
        rotator = pinned_world()
        fresh = rotator.rotate(now=50)
        rotator.pin("api", fresh.serial, now=51)
        page = rotator.report(now=55)
        assert page.splitlines() == [
            "serving serial 2; 1 laggard(s)",
            "  web: breaks in 15",
        ]

    def test_a_current_fleet_reads_clean(self):
        rotator = pinned_world()
        fresh = rotator.rotate(now=50)
        rotator.pin("web", fresh.serial, now=51)
        rotator.pin("api", fresh.serial, now=51)
        assert "every client is current" in rotator.report(now=55)
