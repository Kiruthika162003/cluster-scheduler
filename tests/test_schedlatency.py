from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.schedlatency import BandLatency, LatencyTracker, percentile


class TestPercentile:
    def test_the_median_of_odd_counts_is_the_middle(self):
        assert percentile([1, 2, 9], 0.50) == 2

    def test_p95_reaches_into_the_tail(self):
        values = sorted(range(1, 101))
        assert percentile(values, 0.95) == 95

    def test_no_samples_is_a_named_refusal(self):
        with pytest.raises(Invalid):
            percentile([], 0.5)


class TestTracking:
    def test_offer_to_bind_is_the_wait(self):
        tracker = LatencyTracker()
        tracker.offered("web", priority=100, now=3)
        assert tracker.bound("web", now=10) == 7

    def test_binding_the_unoffered_is_refused(self):
        with pytest.raises(Invalid):
            LatencyTracker().bound("ghost", now=5)

    def test_a_second_offer_does_not_reset_the_clock(self):
        tracker = LatencyTracker()
        tracker.offered("web", priority=100, now=0)
        tracker.offered("web", priority=100, now=8)
        assert tracker.bound("web", now=10) == 10

    def test_bands_keep_separate_books(self):
        tracker = LatencyTracker()
        tracker.offered("urgent", priority=1000, now=0)
        tracker.offered("patient", priority=10, now=0)
        tracker.bound("urgent", now=1)
        tracker.bound("patient", now=200)
        assert tracker.bands["critical"].summary()["worst"] == 1
        assert tracker.bands["batch"].summary()["worst"] == 200

    def test_abandonment_leaves_no_ghost(self):
        tracker = LatencyTracker()
        tracker.offered("web", priority=100, now=0)
        tracker.abandoned("web")
        assert tracker.still_waiting(now=50) == []


class TestSummaries:
    def test_the_three_numbers_an_slo_needs(self):
        band = BandLatency(finished=[1, 2, 3, 4, 100])
        numbers = band.summary()
        assert numbers == {"count": 5, "p50": 3, "p95": 100, "worst": 100}

    def test_the_waiting_are_sorted_oldest_first(self):
        tracker = LatencyTracker()
        tracker.offered("young", priority=100, now=8)
        tracker.offered("old", priority=100, now=0)
        rows = tracker.still_waiting(now=10)
        assert [row[0] for row in rows] == ["old", "young"]
        assert rows[0][2] == 10

    def test_the_report_reads_bands_then_the_waiting(self):
        tracker = LatencyTracker()
        tracker.offered("done", priority=1000, now=0)
        tracker.bound("done", now=2)
        tracker.offered("stuck", priority=10, now=1)
        page = tracker.report(now=21)
        assert "critical: p50=2 p95=2 worst=2 over 1 binds" in page
        assert "stuck (batch) has waited 20" in page

    def test_an_empty_tracker_says_so(self):
        assert LatencyTracker().report(now=0) == "no samples yet"
