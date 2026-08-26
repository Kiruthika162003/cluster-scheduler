from __future__ import annotations

import pytest

from fleet.autosplit import DWELL, Shard, Splitter
from fleet.errors import Invalid


def layout() -> Splitter:
    return Splitter(
        shards=[
            Shard(low=0, high=100),
            Shard(low=100, high=200),
            Shard(low=200, high=300),
        ],
        move_budget=500,
    )


def hot_loads() -> dict[int, int]:
    return {0: 900, 100: 100, 200: 100}


class TestSplitting:
    def test_a_spike_splits_nothing(self):
        splitter = layout()
        assert splitter.observe(hot_loads(), now=0) == []

    def test_sustained_heat_splits_at_the_midpoint(self):
        splitter = layout()
        splitter.observe(hot_loads(), now=0)
        acted = splitter.observe(hot_loads(), now=DWELL)
        assert acted == ["split [0,100) at 50, moved 450 keys"]
        assert splitter.shards[0].name() == "[0,50)"
        assert splitter.shards[1].name() == "[50,100)"

    def test_cooling_off_resets_the_dwell(self):
        splitter = layout()
        splitter.observe(hot_loads(), now=0)
        splitter.observe({0: 100, 100: 100, 200: 100}, now=1)
        acted = splitter.observe(hot_loads(), now=DWELL + 1)
        assert acted == []

    def test_a_split_over_budget_is_refused_with_its_price(self):
        splitter = layout()
        splitter.move_budget = 100
        splitter.observe(hot_loads(), now=0)
        assert splitter.observe(hot_loads(), now=DWELL) == []
        assert "moving 450 keys exceeds budget 100" in splitter.refused[0]


class TestMerging:
    def cold_world(self) -> Splitter:
        return Splitter(
            shards=[
                Shard(low=0, high=100),
                Shard(low=100, high=200),
                Shard(low=200, high=201),
            ],
            move_budget=500,
        )

    def test_two_starving_neighbours_merge_after_the_dwell(self):
        splitter = self.cold_world()
        loads = {0: 5, 100: 5, 200: 1000}
        splitter.observe(loads, now=0)
        acted = splitter.observe(loads, now=DWELL)
        assert acted == ["merged [0,100) and [100,200), moved 5 keys"]
        assert splitter.shards[0].name() == "[0,200)"

    def test_a_lull_merges_nothing(self):
        splitter = self.cold_world()
        loads = {0: 5, 100: 5, 200: 1000}
        assert splitter.observe(loads, now=0) == []
        assert len(splitter.shards) == 3


class TestContracts:
    def test_an_empty_layout_is_refused(self):
        with pytest.raises(Invalid):
            Splitter(shards=[], move_budget=10)

    def test_the_layout_reads_in_order(self):
        splitter = layout()
        splitter.observe({0: 10, 100: 20, 200: 30}, now=0)
        assert splitter.layout() == "[0,100)=10 [100,200)=20 [200,300)=30"
