from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.slo import BurnMeter, SloBoard, SloSpec


def meter(objective: float = 0.99) -> BurnMeter:
    return BurnMeter(spec=SloSpec(name="web", objective=objective, window=1000))


class TestSpec:
    def test_the_objective_must_be_a_fraction(self):
        with pytest.raises(Invalid):
            SloSpec(name="web", objective=99.0, window=30)

    def test_the_budget_is_the_complement(self):
        spec = SloSpec(name="web", objective=0.99, window=30)
        assert spec.budget_fraction == pytest.approx(0.01)


class TestBurnRates:
    def test_a_healthy_service_burns_nothing(self):
        m = meter()
        for tick in range(10):
            m.observe(tick, good=100, total=100)
        assert m.fast_burn(10) == 0.0
        assert m.slow_burn(10) == 0.0

    def test_burning_exactly_the_budget_reads_one(self):
        m = meter()
        for tick in range(10):
            m.observe(tick, good=99, total=100)
        assert m.fast_burn(10) == 1.0

    def test_a_cliff_reads_in_multiples_of_budget(self):
        m = meter()
        for tick in range(5):
            m.observe(tick, good=80, total=100)
        assert m.fast_burn(5) == 20.0

    def test_good_beyond_total_is_refused(self):
        m = meter()
        with pytest.raises(Invalid):
            m.observe(0, good=101, total=100)


class TestAlarming:
    def test_a_short_spike_does_not_alarm(self):
        m = meter()
        for tick in range(55):
            m.observe(tick, good=100, total=100)
        for tick in range(55, 60):
            m.observe(tick, good=0, total=100)
        assert m.fast_burn(60) == 100.0
        assert not m.alarming(60)

    def test_a_sustained_outage_alarms(self):
        m = meter()
        for tick in range(60):
            m.observe(tick, good=50, total=100)
        assert m.alarming(60)

    def test_recovery_clears_the_fast_window_first(self):
        m = meter()
        for tick in range(60):
            m.observe(tick, good=50, total=100)
        for tick in range(60, 66):
            m.observe(tick, good=100, total=100)
        assert m.fast_burn(66) == 0.0
        assert not m.alarming(66)


class TestBudget:
    def test_the_budget_depletes_and_floors_at_zero(self):
        m = meter()
        for tick in range(10):
            m.observe(tick, good=90, total=100)
        assert m.exhausted()
        assert m.budget_left() == 0.0

    def test_old_sins_roll_off_the_window(self):
        m = BurnMeter(spec=SloSpec(name="web", objective=0.99, window=10))
        m.observe(0, good=0, total=100)
        for tick in range(1, 12):
            m.observe(tick, good=100, total=100)
        assert m.budget_left() == 1.0


class TestBoard:
    def test_the_board_freezes_the_bankrupt(self):
        board = SloBoard()
        board.watch(SloSpec(name="web", objective=0.99, window=1000))
        board.watch(SloSpec(name="api", objective=0.99, window=1000))
        for tick in range(10):
            board.observe("web", tick, good=100, total=100)
            board.observe("api", tick, good=50, total=100)
        assert board.frozen_deploys() == ["api"]
        assert "api" in board.report(10)

    def test_watching_nothing_is_a_named_mistake(self):
        board = SloBoard()
        with pytest.raises(Invalid):
            board.observe("ghost", 0, good=1, total=1)
