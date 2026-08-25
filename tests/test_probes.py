from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.probes import DOWN_AFTER, UP_AFTER, Prober


def watched() -> Prober:
    prober = Prober()
    prober.watch("web")
    return prober


class TestEvidence:
    def test_one_clean_round_is_not_up(self):
        prober = watched()
        assert prober.observe("web", 0, latency=12) is None
        assert prober.targets["web"].verdict == "unknown"

    def test_up_needs_its_streak(self):
        prober = watched()
        transition = None
        for tick in range(UP_AFTER):
            transition = prober.observe("web", tick, latency=10)
        assert transition == f"[{UP_AFTER - 1}] -> up ({UP_AFTER} clean rounds)"

    def test_one_dropped_packet_does_not_flip_the_dashboard(self):
        prober = watched()
        for tick in range(UP_AFTER):
            prober.observe("web", tick, latency=10)
        assert prober.observe("web", 5, failure="timeout") is None
        assert prober.targets["web"].verdict == "up"

    def test_down_carries_its_evidence(self):
        prober = watched()
        for tick in range(UP_AFTER):
            prober.observe("web", tick, latency=10)
        transition = None
        for tick in range(10, 10 + DOWN_AFTER):
            transition = prober.observe("web", tick, failure="timeout")
        assert transition == "[12] -> down (timeout, timeout, timeout)"
        assert prober.down() == ["web"]

    def test_a_failure_resets_the_up_streak(self):
        prober = watched()
        prober.observe("web", 0, latency=10)
        prober.observe("web", 1, failure="refused")
        prober.observe("web", 2, latency=10)
        assert prober.targets["web"].verdict == "unknown"


class TestContracts:
    def test_exactly_one_of_latency_or_failure(self):
        prober = watched()
        with pytest.raises(Invalid):
            prober.observe("web", 0)
        with pytest.raises(Invalid):
            prober.observe("web", 0, latency=5, failure="timeout")

    def test_unwatched_targets_are_refused(self):
        with pytest.raises(Invalid):
            Prober().observe("ghost", 0, latency=1)

    def test_double_watching_is_refused(self):
        prober = watched()
        with pytest.raises(Invalid):
            prober.watch("web")


class TestReport:
    def test_the_report_carries_verdicts_and_history(self):
        prober = watched()
        prober.watch("api")
        for tick in range(UP_AFTER):
            prober.observe("web", tick, latency=10 + tick)
            prober.observe("api", tick, latency=50)
        for tick in range(10, 10 + DOWN_AFTER):
            prober.observe("api", tick, failure="refused")
        page = prober.report()
        assert page.startswith("2 targets, 1 down")
        assert "web: up, median 11" in page
        assert "-> down (refused, refused, refused)" in page
