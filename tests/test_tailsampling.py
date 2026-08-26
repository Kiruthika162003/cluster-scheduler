from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.tailsampling import TailSampler, Trace


def day(sampler: TailSampler) -> None:
    """980 boring, 15 slow, 5 failed."""
    for number in range(980):
        sampler.offer(Trace(name=f"ok-{number}", latency=10, failed=False))
    for number in range(15):
        sampler.offer(Trace(name=f"slow-{number}", latency=900, failed=False))
    for number in range(5):
        sampler.offer(Trace(name=f"bad-{number}", latency=10, failed=True))


class TestKeeping:
    def test_errors_are_always_kept(self):
        sampler = TailSampler(slow_line=500, keep_one_in=100)
        outcome = sampler.offer(Trace(name="boom", latency=5, failed=True))
        assert outcome == "kept: error"

    def test_slow_traces_are_always_kept(self):
        sampler = TailSampler(slow_line=500, keep_one_in=100)
        outcome = sampler.offer(Trace(name="crawl", latency=700, failed=False))
        assert outcome == "kept: slow"

    def test_the_boring_are_kept_one_in_n(self):
        sampler = TailSampler(slow_line=500, keep_one_in=10)
        outcomes = [
            sampler.offer(Trace(name=f"t{number}", latency=5, failed=False))
            for number in range(10)
        ]
        assert outcomes.count("dropped") == 9
        assert outcomes.count("kept: 1 in 10") == 1

    def test_zero_knobs_are_refused(self):
        with pytest.raises(Invalid):
            TailSampler(slow_line=0, keep_one_in=10)


class TestEstimation:
    def test_the_store_shrinks_while_the_estimate_holds(self):
        sampler = TailSampler(slow_line=500, keep_one_in=100)
        day(sampler)
        assert sampler.stored() == 29
        assert sampler.estimated_total() == 920
        assert sampler.estimate_error() == 0.08

    def test_interesting_counts_are_exact(self):
        sampler = TailSampler(slow_line=500, keep_one_in=100)
        day(sampler)
        assert sampler.exact_interesting() == 20

    def test_a_finer_sample_shrinks_the_error(self):
        coarse = TailSampler(slow_line=500, keep_one_in=100)
        fine = TailSampler(slow_line=500, keep_one_in=10)
        day(coarse)
        day(fine)
        assert fine.estimate_error() < coarse.estimate_error()

    def test_an_empty_sampler_refuses_to_estimate(self):
        with pytest.raises(Invalid):
            TailSampler(slow_line=500, keep_one_in=10).estimate_error()


class TestHonesty:
    def test_the_blindness_report_names_the_steps(self):
        sampler = TailSampler(slow_line=500, keep_one_in=100)
        day(sampler)
        page = sampler.blindness()
        assert "20 kept at weight 1" in page
        assert "boring 980 is an estimate with steps of 100" in page

    def test_the_statement_reads_the_trade(self):
        sampler = TailSampler(slow_line=500, keep_one_in=100)
        day(sampler)
        assert sampler.statement() == (
            "29 stored of 1000 seen (2.9%), estimated total 920 "
            "(error 8.00%)"
        )
