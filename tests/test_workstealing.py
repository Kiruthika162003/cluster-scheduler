from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.workstealing import StealingPool, Worker, compare

SKEWED = [30, 1, 1] * 4


class TestTheComparison:
    def test_stealing_halves_the_skewed_finish(self):
        result = compare(SKEWED, worker_count=3)
        assert result["static_finish"] == 120
        assert result["stealing_finish"] == 60
        assert result["steals"] == 2
        assert result["bought"] == 60

    def test_the_floor_is_still_out_of_reach(self):
        result = compare(SKEWED, worker_count=3)
        assert result["floor"] == 43
        assert result["stealing_finish"] > result["floor"]

    def test_a_balanced_workload_needs_no_thieves(self):
        result = compare([5, 5, 5, 5], worker_count=2)
        assert result["steals"] == 0
        assert result["bought"] == 0
        assert result["stealing_finish"] == result["floor"]

    def test_zero_workers_are_refused(self):
        with pytest.raises(Invalid):
            compare([1], worker_count=0)


class TestTheMechanics:
    def test_the_thief_takes_from_the_tail(self):
        pool = StealingPool(
            workers=[Worker(name="busy"), Worker(name="idle")],
            stealing=True,
        )
        pool.workers[0].queue = [10, 20, 30]
        pool.run()
        assert pool.steals >= 1
        assert pool.workers[1].done >= 1

    def test_static_pools_never_steal(self):
        pool = StealingPool(
            workers=[Worker(name="busy"), Worker(name="idle")],
            stealing=False,
        )
        pool.workers[0].queue = [10, 20, 30]
        pool.run()
        assert pool.steals == 0
        assert pool.workers[1].done == 0

    def test_an_empty_pool_is_refused(self):
        with pytest.raises(Invalid):
            StealingPool(workers=[])
