from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.queuemodel import (
    compare_to_uniform,
    knee_table,
    measured_wait,
    predict,
)


class TestTheFormula:
    def test_half_utilisation_waits_one_service_time(self):
        prediction = predict(arrival_rate=0.25, service_ticks=2)
        assert prediction.rho == 0.5
        assert prediction.predicted_wait == 2.0

    def test_the_knee_shape_doubles_and_doubles_again(self):
        table = knee_table(2, (0.5, 0.75, 0.87, 0.95))
        assert table.splitlines() == [
            "rho    wait",
            "0.50   2.0",
            "0.75   6.0",
            "0.87   13.385",
            "0.95   38.0",
        ]

    def test_littles_law_holds_exactly(self):
        prediction = predict(arrival_rate=0.25, service_ticks=2)
        assert prediction.predicted_in_flight == 1.0

    def test_saturation_owes_you_no_number(self):
        with pytest.raises(Invalid, match="no formula owes you a number"):
            predict(arrival_rate=0.5, service_ticks=2)

    def test_nonsense_rates_are_refused(self):
        with pytest.raises(Invalid):
            predict(arrival_rate=0.0, service_ticks=2)


class TestAgainstTheGenerator:
    def test_uniform_arrivals_wait_nothing_at_half_load(self):
        assert measured_wait(service_ticks=2, every=4, duration=2000) == 0.0

    def test_the_comparison_names_the_missing_variance(self):
        verdict = compare_to_uniform(service_ticks=2, every=4)
        assert verdict == (
            "uniform arrivals wait 0.0 against the random-arrival "
            "story of 2.0: the formula prices variance you do not have"
        )

    def test_the_formula_is_a_story_about_variance_not_queues(self):
        prediction = predict(arrival_rate=0.25, service_ticks=2)
        measured = measured_wait(service_ticks=2, every=4, duration=2000)
        assert measured < prediction.predicted_wait
