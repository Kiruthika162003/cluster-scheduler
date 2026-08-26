from __future__ import annotations

import pytest

from fleet.adaptiveconcurrency import BACKOFF, FLOOR, AdaptiveLimit
from fleet.errors import Invalid


class TestAdmission:
    def test_the_limit_caps_in_flight(self):
        limiter = AdaptiveLimit(latency_target=100, limit=2.0)
        assert limiter.admit()
        assert limiter.admit()
        assert not limiter.admit()
        assert limiter.refused == 1

    def test_observations_free_the_slot(self):
        limiter = AdaptiveLimit(latency_target=100, limit=1.0)
        limiter.admit()
        limiter.observe(latency=50)
        assert limiter.admit()

    def test_observing_without_admitting_is_refused(self):
        with pytest.raises(Invalid):
            AdaptiveLimit(latency_target=100).observe(latency=10)


class TestAimd:
    def test_healthy_latency_grows_additively(self):
        limiter = AdaptiveLimit(latency_target=100, limit=4.0)
        for _ in range(4):
            limiter.admit()
            limiter.observe(latency=50)
        assert limiter.limit == 6.0

    def test_congestion_cuts_multiplicatively(self):
        limiter = AdaptiveLimit(latency_target=100, limit=10.0)
        limiter.admit()
        limiter.observe(latency=500)
        assert limiter.limit == 10.0 * BACKOFF

    def test_the_floor_keeps_one_probe_alive(self):
        limiter = AdaptiveLimit(latency_target=100, limit=1.0)
        for _ in range(10):
            limiter.admit()
            limiter.observe(latency=500)
        assert limiter.limit == FLOOR
        assert limiter.admit()

    def test_the_sawtooth_emerges_from_a_congested_knee(self):
        limiter = AdaptiveLimit(latency_target=100, limit=4.0)
        for _ in range(60):
            limiter.admit()
            latency = 50 if limiter.limit < 8 else 300
            limiter.observe(latency=latency)
        assert 4 <= limiter.ceiling() <= 8
        teeth = sum(
            1
            for before, after in zip(
                limiter.history, limiter.history[1:], strict=False
            )
            if after < before
        )
        assert teeth >= 5

    def test_the_summary_reads_the_sweep(self):
        limiter = AdaptiveLimit(latency_target=100, limit=4.0)
        limiter.admit()
        limiter.observe(latency=50)
        limiter.admit()
        limiter.observe(latency=500)
        line = limiter.sawtooth()
        assert "with 1 backoffs" in line
        assert AdaptiveLimit(latency_target=1).sawtooth() == "no observations"
