from __future__ import annotations

import pytest

from fleet.clockskew import SkewTracker
from fleet.errors import Invalid


class TestEstimation:
    def test_a_symmetric_echo_reads_the_offset_exactly(self):
        tracker = SkewTracker()
        estimate = tracker.echo("n1", sent=100, peer_stamp=155, received=110)
        assert estimate.offset == 50.0
        assert estimate.error == 5.0

    def test_a_perfect_clock_measures_zero(self):
        tracker = SkewTracker()
        estimate = tracker.echo("n1", sent=100, peer_stamp=105, received=110)
        assert estimate.offset == 0.0

    def test_time_travel_replies_are_refused(self):
        with pytest.raises(Invalid):
            SkewTracker().echo("n1", sent=100, peer_stamp=105, received=90)

    def test_the_bound_ages_with_drift(self):
        tracker = SkewTracker()
        estimate = tracker.echo("n1", sent=100, peer_stamp=155, received=110)
        assert estimate.error_at(110) == 5.0
        assert estimate.error_at(610) == 6.0


class TestTranslation:
    def test_peer_stamps_translate_back_to_local(self):
        tracker = SkewTracker()
        tracker.echo("n1", sent=100, peer_stamp=155, received=110)
        local, error = tracker.to_local("n1", stamp=200, now=110)
        assert local == 150.0
        assert error == 5.0

    def test_the_unmeasured_are_refused(self):
        with pytest.raises(Invalid):
            SkewTracker().to_local("ghost", stamp=1, now=0)


class TestOrdering:
    def build(self) -> SkewTracker:
        tracker = SkewTracker()
        tracker.echo("n1", sent=100, peer_stamp=155, received=102)
        tracker.echo("n2", sent=100, peer_stamp=71, received=102)
        return tracker

    def test_a_wide_gap_orders_confidently(self):
        tracker = self.build()
        verdict = tracker.ordered("n1", 200, "n2", 200, now=102)
        assert verdict == "yes"

    def test_the_reverse_reads_no(self):
        tracker = self.build()
        verdict = tracker.ordered("n2", 200, "n1", 200, now=102)
        assert verdict == "no"

    def test_the_close_call_refuses_to_guess(self):
        tracker = self.build()
        verdict = tracker.ordered("n1", 200, "n2", 117, now=102)
        assert verdict == "too close to call"

    def test_stale_estimates_widen_into_humility(self):
        tracker = self.build()
        confident = tracker.ordered("n1", 200, "n2", 121, now=102)
        humble = tracker.ordered("n1", 200, "n2", 121, now=2000)
        assert confident == "yes"
        assert humble == "too close to call"


class TestReport:
    def test_the_report_prints_age_adjusted_bounds(self):
        tracker = SkewTracker()
        tracker.echo("n1", sent=100, peer_stamp=155, received=110)
        page = tracker.report(now=610)
        assert page == "n1: offset +50.0 within 6.0 (measured at 110)"
        assert SkewTracker().report(now=0) == "no peers measured"
