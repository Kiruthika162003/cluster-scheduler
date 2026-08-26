from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.outliers import (
    compare,
    mad,
    median,
    robust_outliers,
    zscore_outliers,
)


def spiked_fleet() -> dict[str, float]:
    fleet = {f"n{number}": 10.0 + (number % 3) for number in range(9)}
    fleet["n9"] = 400.0
    return fleet


class TestRobustStats:
    def test_the_median_ignores_the_spike(self):
        assert median([10, 10, 11, 400]) == 10.5

    def test_mad_measures_the_healthy_spread(self):
        assert mad([10, 10, 11, 400]) == 0.5

    def test_no_values_is_refused(self):
        with pytest.raises(Invalid):
            median([])


class TestDetection:
    def test_the_spike_is_flagged_with_its_score(self):
        found = robust_outliers(spiked_fleet())
        assert [outlier.name for outlier in found] == ["n9"]
        assert found[0].robust_score == 262.38

    def test_the_zscore_detector_misses_the_same_spike(self):
        assert zscore_outliers(spiked_fleet()) == []

    def test_the_comparison_is_the_argument(self):
        assert compare(spiked_fleet()) == (
            "robust flags ['n9'], z-score flags []"
        )

    def test_a_healthy_fleet_flags_nobody(self):
        fleet = {f"n{number}": 10.0 + (number % 3) for number in range(10)}
        assert robust_outliers(fleet) == []

    def test_tiny_fleets_are_refused_not_judged(self):
        with pytest.raises(Invalid):
            robust_outliers({"a": 1.0, "b": 2.0, "c": 3.0})

    def test_an_identical_fleet_with_one_dissenter(self):
        fleet = {f"n{number}": 10.0 for number in range(9)}
        fleet["odd"] = 11.0
        found = robust_outliers(fleet)
        assert [outlier.name for outlier in found] == ["odd"]
        assert found[0].robust_score == float("inf")
