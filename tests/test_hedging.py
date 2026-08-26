from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.hedging import Hedger


def slow_tail_world(hedger: Hedger) -> None:
    """95 fast calls at 10, five stragglers at 200; backups always 10."""
    for _ in range(95):
        hedger.call(primary_latency=10, backup_latency=10)
    for _ in range(5):
        hedger.call(primary_latency=200, backup_latency=10)


class TestTheRace:
    def test_a_fast_primary_never_hedges(self):
        hedger = Hedger(hedge_delay=50)
        outcome = hedger.call(primary_latency=10, backup_latency=10)
        assert not outcome.hedged
        assert outcome.delivered == 10

    def test_a_straggler_is_beaten_by_the_backup(self):
        hedger = Hedger(hedge_delay=50)
        outcome = hedger.call(primary_latency=200, backup_latency=10)
        assert outcome.hedged
        assert outcome.winner == "backup"
        assert outcome.delivered == 60

    def test_the_primary_can_still_win_the_race(self):
        hedger = Hedger(hedge_delay=50)
        outcome = hedger.call(primary_latency=55, backup_latency=100)
        assert outcome.hedged
        assert outcome.winner == "primary"
        assert outcome.delivered == 55

    def test_a_negative_delay_is_refused(self):
        with pytest.raises(Invalid):
            Hedger(hedge_delay=-1)


class TestTheTrade:
    def test_the_tail_is_bought(self):
        hedger = Hedger(hedge_delay=50)
        slow_tail_world(hedger)
        p99_before = hedger.percentile(hedger.unhedged_latencies(), 0.99)
        p99_after = hedger.percentile(hedger.delivered_latencies(), 0.99)
        assert p99_before == 200
        assert p99_after == 60

    def test_only_the_tail_pays(self):
        hedger = Hedger(hedge_delay=50)
        slow_tail_world(hedger)
        assert hedger.extra_load() == 0.05

    def test_delay_zero_is_a_traffic_doubling(self):
        hedger = Hedger(hedge_delay=0)
        slow_tail_world(hedger)
        assert hedger.extra_load() == 1.0

    def test_the_trade_reads_both_sides(self):
        hedger = Hedger(hedge_delay=50)
        slow_tail_world(hedger)
        assert hedger.trade() == "p99 200 -> 60 for 5.0% extra load"

    def test_no_calls_is_a_named_refusal(self):
        with pytest.raises(Invalid):
            Hedger(hedge_delay=10).trade()
