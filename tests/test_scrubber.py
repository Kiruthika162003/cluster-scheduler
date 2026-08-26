from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.scrubber import Scrubber, rate_for_promise


def guarded(count: int = 100, rate: int = 10) -> Scrubber:
    return Scrubber(
        blocks=[f"b{number}" for number in range(count)], rate=rate
    )


class TestTheWalk:
    def test_the_walk_is_bounded_per_tick(self):
        scrubber = guarded()
        scrubber.tick(now=0)
        assert scrubber.verified == 10

    def test_the_cycle_wraps_and_counts(self):
        scrubber = guarded(count=25, rate=10)
        for tick in range(5):
            scrubber.tick(now=tick)
        assert scrubber.cycles_completed == 2

    def test_corruption_is_found_within_one_cycle(self):
        scrubber = guarded(count=100, rate=10)
        scrubber.mark_corrupt("b95")
        found_at = None
        for tick in range(scrubber.cycle_ticks()):
            if scrubber.tick(now=tick):
                found_at = tick
                break
        assert found_at == 9

    def test_the_find_is_stamped_for_mttd(self):
        scrubber = guarded(count=10, rate=10)
        scrubber.mark_corrupt("b3")
        scrubber.tick(now=42)
        assert scrubber.repair_queue == [("b3", 42)]

    def test_marking_a_foreign_block_is_refused(self):
        with pytest.raises(Invalid):
            guarded().mark_corrupt("elsewhere")

    def test_empty_or_lazy_scrubbers_are_refused(self):
        with pytest.raises(Invalid):
            Scrubber(blocks=[], rate=1)
        with pytest.raises(Invalid):
            Scrubber(blocks=["b0"], rate=0)


class TestThePromise:
    def test_the_promise_is_blocks_over_rate(self):
        scrubber = guarded(count=100, rate=10)
        assert scrubber.cycle_ticks() == 10
        assert scrubber.detection_promise() == (
            "any corruption surfaces within 10 ticks "
            "(100 blocks at 10/tick)"
        )

    def test_growing_the_fleet_stretches_the_promise(self):
        assert guarded(count=200, rate=10).cycle_ticks() == 20

    def test_the_planner_inverts_the_arithmetic(self):
        assert rate_for_promise(block_count=100, within_ticks=10) == 10
        assert rate_for_promise(block_count=101, within_ticks=10) == 11

    def test_nonsense_promises_are_refused(self):
        with pytest.raises(Invalid):
            rate_for_promise(block_count=0, within_ticks=10)
