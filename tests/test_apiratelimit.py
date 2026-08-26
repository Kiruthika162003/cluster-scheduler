from __future__ import annotations

import pytest

from fleet.apiratelimit import Bucket, Limiter
from fleet.errors import Invalid


def limiter(reserve_burst: int = 10) -> Limiter:
    built = Limiter(reserve=Bucket(rate=1.0, burst=reserve_burst))
    built.register("ui", rate=1.0, burst=3)
    built.register("batch", rate=0.5, burst=2)
    return built


class TestBuckets:
    def test_a_bucket_starts_full(self):
        bucket = Bucket(rate=1.0, burst=3)
        assert [bucket.take(0) for _ in range(4)] == [True, True, True, False]

    def test_refill_is_paced_by_the_rate(self):
        bucket = Bucket(rate=0.5, burst=2)
        for _ in range(2):
            bucket.take(0)
        assert not bucket.take(1)
        assert bucket.take(2)

    def test_retry_after_is_arithmetic_not_a_guess(self):
        bucket = Bucket(rate=0.5, burst=2)
        for _ in range(2):
            bucket.take(0)
        assert bucket.wait_for_one(0) == 2

    def test_nonsense_rates_are_refused(self):
        with pytest.raises(Invalid):
            Bucket(rate=0.0, burst=1)


class TestTheReserve:
    def test_a_burst_beyond_the_bucket_draws_the_reserve(self):
        gate = limiter()
        outcomes = [gate.allow("ui", 0)[0] for _ in range(6)]
        assert outcomes == [True] * 6

    def test_the_reserve_floor_stops_the_flood(self):
        gate = limiter(reserve_burst=4)
        outcomes = [gate.allow("ui", 0)[0] for _ in range(8)]
        assert outcomes.count(True) == 5
        allowed, retry = gate.allow("ui", 0)
        assert not allowed
        assert retry == 1

    def test_unregistered_clients_are_a_named_mistake(self):
        with pytest.raises(Invalid):
            limiter().allow("ghost", 0)


class TestStarvation:
    def test_acceptance_resets_the_streak(self):
        gate = limiter(reserve_burst=4)
        for _ in range(9):
            gate.allow("ui", 0)
        assert gate.refused_streak["ui"] > 0
        gate.allow("ui", 50)
        assert gate.refused_streak["ui"] == 0

    def test_the_missized_bucket_is_diagnosed_not_blamed(self):
        gate = Limiter(reserve=Bucket(rate=1.0, burst=3), reserve_floor=3.0)
        gate.register("tiny", rate=0.01, burst=1)
        gate.register("big", rate=100.0, burst=100)
        gate.allow("tiny", 0)
        for tick in range(1, 30):
            gate.allow("big", tick)
        for tick in range(30, 36):
            gate.allow("tiny", tick)
        diagnosis = gate.diagnosis()
        assert "tiny" in diagnosis
        assert "mis-sized" in diagnosis

    def test_real_pressure_reads_differently(self):
        gate = Limiter(reserve=Bucket(rate=0.1, burst=3), reserve_floor=3.0)
        gate.register("a", rate=0.01, burst=1)
        gate.register("b", rate=0.01, burst=1)
        for _ in range(20):
            gate.allow("a", 0)
            gate.allow("b", 0)
        diagnosis = gate.diagnosis()
        assert "under real pressure" in diagnosis
