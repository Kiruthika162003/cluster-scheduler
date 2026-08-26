from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.quantilesketch import Reservoir, exact_quantile, measured_error

STREAM = [float((7919 * number) % 10000) for number in range(10000)]


class TestTheReservoir:
    def test_it_holds_at_most_its_size(self):
        reservoir = Reservoir(size=500)
        for value in STREAM:
            reservoir.offer(value)
        assert len(reservoir.slots) == 500
        assert reservoir.seen == 10000

    def test_small_streams_are_kept_exactly(self):
        reservoir = Reservoir(size=100)
        for value in (5.0, 1.0, 9.0):
            reservoir.offer(value)
        assert reservoir.quantile(0.5) == 5.0

    def test_runs_reproduce(self):
        first = Reservoir(size=50)
        second = Reservoir(size=50)
        for value in STREAM[:1000]:
            first.offer(value)
            second.offer(value)
        assert first.slots == second.slots

    def test_an_empty_reservoir_answers_nothing(self):
        with pytest.raises(Invalid):
            Reservoir(size=10).quantile(0.5)

    def test_zero_room_is_refused(self):
        with pytest.raises(Invalid):
            Reservoir(size=0)

    def test_quantiles_are_fractions(self):
        reservoir = Reservoir(size=10)
        reservoir.offer(1.0)
        with pytest.raises(Invalid):
            reservoir.quantile(1.5)


class TestTheHonesty:
    def test_the_error_is_a_number_not_a_hope(self):
        assert measured_error(STREAM, size=500, fraction=0.5) == 0.81
        assert measured_error(STREAM, size=500, fraction=0.95) == 0.29
        assert measured_error(STREAM, size=500, fraction=0.99) == 0.18

    def test_more_slots_buy_less_error(self):
        coarse = measured_error(STREAM, size=50, fraction=0.5)
        fine = measured_error(STREAM, size=2000, fraction=0.5)
        assert fine < coarse

    def test_the_exact_answer_anchors_the_comparison(self):
        assert exact_quantile([1.0, 2.0, 3.0, 4.0], 0.5) == 3.0
        with pytest.raises(Invalid):
            exact_quantile([], 0.5)
