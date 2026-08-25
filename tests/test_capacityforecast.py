from __future__ import annotations

import pytest

from fleet.capacityforecast import UsageLog, fit, time_to_full
from fleet.errors import Invalid


class TestTheFit:
    def test_a_perfect_line_is_recovered_exactly(self):
        trend = fit([(0, 100), (10, 200), (20, 300)])
        assert trend.slope == 10.0
        assert trend.intercept == 100.0
        assert trend.spread == 0.0

    def test_noise_widens_the_spread_not_the_slope(self):
        trend = fit([(0, 95), (10, 205), (20, 295), (30, 405)])
        assert 9.0 < trend.slope < 11.0
        assert trend.spread > 0

    def test_one_sample_is_refused(self):
        with pytest.raises(Invalid):
            fit([(0, 100)])

    def test_a_vertical_stack_is_refused(self):
        with pytest.raises(Invalid):
            fit([(5, 100), (5, 200)])


class TestTimeToFull:
    def test_the_crossing_is_where_the_line_meets_capacity(self):
        trend = fit([(0, 100), (10, 200)])
        forecast = time_to_full(trend, capacity=1000, now=10)
        assert forecast.verdict == "filling"
        assert forecast.full_at == 90
        assert forecast.earliest == 90
        assert forecast.latest == 90

    def test_noise_turns_the_point_into_a_window(self):
        trend = fit([(0, 90), (10, 210), (20, 290), (30, 410)])
        forecast = time_to_full(trend, capacity=1000, now=30)
        assert forecast.earliest < forecast.full_at < forecast.latest

    def test_shrinking_usage_never_fills(self):
        trend = fit([(0, 500), (10, 400)])
        forecast = time_to_full(trend, capacity=1000, now=10)
        assert forecast.verdict == "shrinking"
        assert "never fills" in forecast.line()

    def test_flat_usage_is_its_own_verdict(self):
        trend = fit([(0, 500), (10, 500)])
        forecast = time_to_full(trend, capacity=1000, now=10)
        assert forecast.verdict == "flat"

    def test_a_past_crossing_clamps_to_now(self):
        trend = fit([(0, 900), (10, 1100)])
        forecast = time_to_full(trend, capacity=1000, now=50)
        assert forecast.full_at == 50

    def test_nonsense_capacity_is_refused(self):
        trend = fit([(0, 1), (1, 2)])
        with pytest.raises(Invalid):
            time_to_full(trend, capacity=0, now=0)


class TestTheLog:
    def test_old_samples_roll_off(self):
        log = UsageLog(window=10)
        log.record(0, 100)
        log.record(20, 300)
        log.record(25, 350)
        assert len(log.samples) == 2

    def test_the_log_forecasts_end_to_end(self):
        log = UsageLog()
        for tick in range(0, 50, 10):
            log.record(tick, 100 + tick * 10)
        forecast = log.forecast(capacity=2000, now=40)
        assert forecast.verdict == "filling"
        assert forecast.full_at == 190
        assert "full around tick 190" in forecast.line()
