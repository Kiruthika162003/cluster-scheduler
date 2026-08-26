from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.watermarks import WatermarkStream


def stream(**overrides) -> WatermarkStream:
    settings = {"window_size": 10, "allowance": 3, "late_policy": "correct"}
    settings.update(overrides)
    return WatermarkStream(**settings)


class TestTheWatermark:
    def test_the_watermark_trails_by_the_allowance(self):
        s = stream()
        s.accept(event_time=20, value=1)
        assert s.watermark == 17

    def test_the_watermark_never_retreats(self):
        s = stream()
        s.accept(event_time=20, value=1)
        s.accept(event_time=18, value=1)
        assert s.watermark == 17

    def test_windows_close_when_the_watermark_passes(self):
        s = stream()
        s.accept(event_time=5, value=10)
        s.accept(event_time=9, value=10)
        assert s.closed_totals() == {}
        s.accept(event_time=13, value=1)
        assert s.closed_totals() == {0: 20}

    def test_out_of_order_inside_the_allowance_is_on_time(self):
        s = stream()
        s.accept(event_time=20, value=1)
        outcome = s.accept(event_time=18, value=5)
        assert outcome == "on time"


class TestStragglers:
    def test_a_correction_is_flagged_never_silent(self):
        s = stream()
        s.accept(event_time=9, value=10)
        s.accept(event_time=13, value=1)
        outcome = s.accept(event_time=2, value=5)
        assert outcome == "corrected a closed window (8 late)"
        assert s.windows[0].total == 15
        assert s.windows[0].corrections == 1

    def test_the_drop_policy_counts_its_losses(self):
        s = stream(late_policy="drop")
        s.accept(event_time=9, value=10)
        s.accept(event_time=13, value=1)
        outcome = s.accept(event_time=2, value=5)
        assert outcome.startswith("dropped")
        assert s.dropped == 1
        assert s.windows[0].total == 10

    def test_negative_event_times_are_refused(self):
        with pytest.raises(Invalid):
            stream().accept(event_time=-1, value=1)

    def test_unknown_policies_are_refused(self):
        with pytest.raises(Invalid):
            stream(late_policy="pray")


class TestTuning:
    def test_the_histogram_prices_a_bigger_allowance(self):
        s = stream(allowance=0)
        s.accept(event_time=10, value=1)
        for late in (8, 6, 2):
            s.accept(event_time=10 - late, value=1)
        assert s.allowance_that_catches(1.0) == 8
        assert s.allowance_that_catches(0.67) == 6

    def test_no_stragglers_keeps_the_current_allowance(self):
        s = stream(allowance=3)
        s.accept(event_time=5, value=1)
        assert s.allowance_that_catches(0.9) == 3

    def test_the_report_counts_the_whole_story(self):
        s = stream()
        s.accept(event_time=9, value=10)
        s.accept(event_time=13, value=1)
        s.accept(event_time=2, value=5)
        assert s.report() == (
            "watermark 10, 1 windows closed, 1 stragglers "
            "(0 dropped, 1 windows corrected)"
        )
