from __future__ import annotations

from fleet.differential import Differential


class TestDifferential:
    def test_eighty_random_workloads_agree_exactly(self):
        diff = Differential()
        divergences = diff.campaign(seeds=80)
        assert divergences == 0
        assert diff.runs == 80

    def test_the_comparison_is_deterministic(self):
        one = Differential()
        one.compare(seed=5)
        two = Differential()
        two.compare(seed=5)
        assert len(one.divergences) == len(two.divergences)

    def test_shapes_vary_across_seeds(self):
        diff = Differential()
        shapes = {tuple(diff._shape(seed)[0]) for seed in range(10)}
        assert len(shapes) > 3
