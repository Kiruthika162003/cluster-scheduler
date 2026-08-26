from __future__ import annotations

import pytest

from fleet.brownout import RESTORE_HOLD, Ladder, Stage
from fleet.errors import Invalid


def ladder() -> Ladder:
    return Ladder(
        stages=[
            Stage(feature="recommendations", shed_at=0.7, restore_at=0.5),
            Stage(feature="search-filters", shed_at=0.8, restore_at=0.6),
            Stage(feature="images", shed_at=0.9, restore_at=0.7),
        ]
    )


class TestShedding:
    def test_rising_load_sheds_the_expendable_first(self):
        rungs = ladder()
        rungs.observe(0.75, now=0)
        assert rungs.serving() == ["search-filters", "images"]

    def test_a_cliff_sheds_everything_at_once(self):
        rungs = ladder()
        actions = rungs.observe(0.95, now=0)
        assert len(actions) == 3
        assert rungs.mode() == "core only"

    def test_the_dead_zone_does_not_flap(self):
        rungs = ladder()
        rungs.observe(0.75, now=0)
        rungs.observe(0.65, now=1)
        assert "recommendations" in rungs.shed
        rungs.observe(0.75, now=2)
        assert len(rungs.ledger) == 1


class TestRestoring:
    def test_restore_waits_out_the_hold(self):
        rungs = ladder()
        rungs.observe(0.75, now=0)
        for tick in range(1, 1 + RESTORE_HOLD):
            assert rungs.observe(0.4, now=tick) == []
        actions = rungs.observe(0.4, now=1 + RESTORE_HOLD)
        assert actions == [
            f"[{1 + RESTORE_HOLD}] restored recommendations at load 0.40"
        ]

    def test_a_dip_that_returns_resets_the_hold(self):
        rungs = ladder()
        rungs.observe(0.75, now=0)
        rungs.observe(0.4, now=1)
        rungs.observe(0.65, now=2)
        rungs.observe(0.4, now=3)
        assert rungs.observe(0.4, now=3 + RESTORE_HOLD - 1) == []
        assert rungs.observe(0.4, now=3 + RESTORE_HOLD) != []

    def test_the_hold_counts_from_the_first_calm_reading(self):
        rungs = ladder()
        rungs.observe(0.75, now=0)
        rungs.observe(0.4, now=10)
        assert rungs.observe(0.4, now=10 + RESTORE_HOLD) != []

    def test_restores_come_expendable_last(self):
        rungs = ladder()
        rungs.observe(0.95, now=0)
        rungs.observe(0.3, now=1)
        actions = rungs.observe(0.3, now=1 + RESTORE_HOLD)
        restored = [line.split("restored ")[1].split(" at")[0]
                    for line in actions]
        assert restored == ["recommendations", "search-filters", "images"]


class TestContracts:
    def test_an_inverted_stage_is_refused(self):
        with pytest.raises(Invalid, match="flaps"):
            Stage(feature="x", shed_at=0.5, restore_at=0.6)

    def test_misordered_stages_are_refused(self):
        with pytest.raises(Invalid, match="expendable-first"):
            Ladder(
                stages=[
                    Stage(feature="a", shed_at=0.9, restore_at=0.5),
                    Stage(feature="b", shed_at=0.7, restore_at=0.4),
                ]
            )

    def test_the_timeline_reads_with_numbers(self):
        rungs = ladder()
        rungs.observe(0.75, now=3)
        page = rungs.timeline()
        assert page == "[3] shed recommendations at load 0.75"
        assert Ladder(stages=[]).timeline() == "never browned out"
