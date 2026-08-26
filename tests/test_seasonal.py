from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.seasonal import (
    HOURS_PER_WEEK,
    SeasonalBaseline,
    global_threshold_judge,
)


def trained(weeks: int = 6) -> SeasonalBaseline:
    """Days pulse 100 at night to 1000 at the peak, per learned week."""
    baseline = SeasonalBaseline()
    for week in range(weeks):
        for hour in range(HOURS_PER_WEEK):
            of_day = hour % 24
            value = 100.0 if of_day < 6 else 1000.0
            baseline.learn(week * HOURS_PER_WEEK + hour, value)
    return baseline


class TestLearning:
    def test_slots_wrap_by_the_week(self):
        baseline = SeasonalBaseline()
        assert baseline.slot_of(3) == baseline.slot_of(HOURS_PER_WEEK + 3)

    def test_history_is_bounded_per_slot(self):
        baseline = trained(weeks=20)
        assert baseline.weeks_learned() == 8

    def test_thin_history_refuses_to_judge(self):
        baseline = trained(weeks=2)
        verdict = baseline.judge(3, 100.0)
        assert verdict.startswith("unjudgeable")


class TestJudging:
    def test_the_nightly_lull_is_normal_at_night(self):
        baseline = trained()
        assert baseline.judge(3, 105.0) == "normal for this hour"

    def test_the_same_reading_at_peak_is_a_hole(self):
        baseline = trained()
        verdict = baseline.judge(12, 105.0)
        assert verdict.startswith("hole: 105.0 against a slot median of 1000.0")

    def test_a_spike_against_the_slot_is_a_surge(self):
        baseline = trained()
        verdict = baseline.judge(3, 400.0)
        assert verdict.startswith("surge: 400.0")

    def test_the_global_floor_sleeps_through_the_peak_hole(self):
        verdict = global_threshold_judge(value=450.0, peak=1000.0)
        assert verdict == "fine by the global floor"
        baseline = trained()
        assert baseline.judge(12, 450.0).startswith("hole")

    def test_the_global_floor_pages_every_night(self):
        verdict = global_threshold_judge(value=100.0, peak=1000.0)
        assert verdict.startswith("alert")
        baseline = trained()
        assert baseline.judge(3, 100.0) == "normal for this hour"

    def test_nonsense_peaks_are_refused(self):
        with pytest.raises(Invalid):
            global_threshold_judge(value=1.0, peak=0.0)
