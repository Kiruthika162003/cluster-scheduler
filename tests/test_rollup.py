from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.rollup import Ladder, Point, Rung, fold


class TestFolding:
    def test_a_fold_keeps_the_spike(self):
        points = [Point.raw(0, 1.0), Point.raw(1, 99.0), Point.raw(2, 1.0)]
        merged = fold(points, tick=2)
        assert merged.high == 99.0
        assert merged.low == 1.0
        assert merged.mean == pytest.approx(33.6667, abs=0.001)
        assert merged.weight == 3

    def test_folding_folds_respects_weights(self):
        heavy = fold([Point.raw(0, 10.0)] * 9, tick=0)
        light = Point.raw(1, 100.0)
        merged = fold([heavy, light], tick=1)
        assert merged.mean == 19.0

    def test_folding_nothing_is_refused(self):
        with pytest.raises(Invalid):
            fold([], tick=0)


class TestTheLadder:
    def test_the_footprint_is_bounded(self):
        ladder = Ladder()
        for tick in range(10000):
            ladder.record(tick, 1.0)
        assert ladder.footprint() <= 60 * 3 + 10

    def test_recent_queries_get_raw_resolution(self):
        ladder = Ladder()
        for tick in range(100):
            ladder.record(tick, float(tick))
        points = ladder.query(since=95, now=100)
        assert [point.tick for point in points] == [95, 96, 97, 98, 99]
        assert all(point.weight == 1 for point in points)

    def test_old_queries_get_the_coarser_rung(self):
        ladder = Ladder()
        for tick in range(300):
            ladder.record(tick, 1.0)
        points = ladder.query(since=0, now=300)
        assert points
        assert all(point.weight == 10 for point in points)

    def test_the_spike_outlives_its_raw_sample(self):
        ladder = Ladder()
        for tick in range(500):
            ladder.record(tick, 200.0 if tick == 10 else 1.0)
        assert ladder.spike_survives(threshold=200.0)

    def test_the_mean_alone_would_have_erased_it(self):
        ladder = Ladder()
        for tick in range(500):
            ladder.record(tick, 200.0 if tick == 10 else 1.0)
        folded = [
            point
            for rung in ladder.rungs[1:]
            for point in rung.points
            if point.high == 200.0
        ]
        assert folded
        assert all(point.mean < 25.0 for point in folded)

    def test_beyond_the_ladder_data_is_gone_and_counted(self):
        ladder = Ladder(
            rungs=[Rung(span=1, capacity=5), Rung(span=5, capacity=2)]
        )
        for tick in range(100):
            ladder.record(tick, 1.0)
        assert ladder.folded_away > 0
        assert ladder.footprint() <= 5 + 2 + 5
