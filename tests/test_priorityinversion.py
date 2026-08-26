from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.priorityinversion import InversionGuard


def classic() -> InversionGuard:
    guard = InversionGuard()
    guard.track("checkout", 1000)
    guard.track("report-gen", 0)
    guard.track("web-worker", 100)
    guard.acquires("report-gen", "warehouse-lock")
    guard.blocks_on("checkout", "warehouse-lock")
    return guard


class TestDetection:
    def test_the_classic_shape_is_flagged(self):
        found = classic().inversions()
        assert len(found) == 1
        assert found[0].line() == (
            "checkout (critical) waits on warehouse-lock held by "
            "report-gen (scavenger)"
        )

    def test_same_band_waiting_is_not_inversion(self):
        guard = InversionGuard()
        guard.track("a", 100)
        guard.track("b", 110)
        guard.acquires("b", "lock")
        guard.blocks_on("a", "lock")
        assert guard.inversions() == []

    def test_waiting_on_your_superior_is_fine(self):
        guard = InversionGuard()
        guard.track("batch", 10)
        guard.track("critical", 1000)
        guard.acquires("critical", "lock")
        guard.blocks_on("batch", "lock")
        assert guard.inversions() == []

    def test_blocking_on_the_unheld_is_named(self):
        guard = InversionGuard()
        guard.track("a", 100)
        with pytest.raises(Invalid):
            guard.blocks_on("a", "ghost-lock")

    def test_double_acquisition_is_refused(self):
        guard = classic()
        guard.track("thief", 100)
        with pytest.raises(Invalid):
            guard.acquires("thief", "warehouse-lock")


class TestInheritance:
    def test_the_holder_borrows_the_waiters_rank(self):
        guard = classic()
        actions = guard.inherit(now=5)
        assert actions == [
            "[5] report-gen inherits priority 1000 from checkout"
        ]
        assert guard.priorities["report-gen"] == 1000

    def test_the_shield_blocks_the_middle_task(self):
        guard = classic()
        assert guard.preemptable_by("report-gen", 100)
        guard.inherit(now=5)
        assert not guard.preemptable_by("report-gen", 100)

    def test_release_returns_the_loan_and_frees_the_waiters(self):
        guard = classic()
        guard.inherit(now=5)
        guard.releases("report-gen", now=9)
        assert guard.priorities["report-gen"] == 0
        assert guard.waiting == {}
        assert guard.journal[-1] == (
            "[9] report-gen returns its borrowed priority, back to 0"
        )

    def test_inheritance_is_idempotent(self):
        guard = classic()
        guard.inherit(now=5)
        assert guard.inherit(now=6) == []

    def test_releasing_nothing_is_refused(self):
        with pytest.raises(Invalid):
            classic().releases("checkout", now=1)
