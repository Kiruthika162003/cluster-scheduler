from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.singleflight import SingleFlight


class TestBoarding:
    def test_the_first_caller_flies(self):
        group = SingleFlight()
        assert group.ask("a", "user:42") == "fly"

    def test_the_rest_wait_on_the_leader(self):
        group = SingleFlight()
        group.ask("a", "user:42")
        assert group.ask("b", "user:42") == "wait: a is flying user:42"
        assert group.trips_saved == 1

    def test_different_keys_fly_separately(self):
        group = SingleFlight()
        assert group.ask("a", "user:42") == "fly"
        assert group.ask("b", "user:7") == "fly"
        assert group.trips_flown == 2

    def test_double_boarding_is_refused(self):
        group = SingleFlight()
        group.ask("a", "user:42")
        with pytest.raises(Invalid):
            group.ask("a", "user:42")


class TestLanding:
    def test_the_answer_is_shared_with_everyone_aboard(self):
        group = SingleFlight()
        group.ask("a", "user:42")
        group.ask("b", "user:42")
        group.ask("c", "user:42")
        told = group.land("user:42", outcome="row-42")
        assert told == ["a", "b", "c"]
        assert group.in_flight() == []

    def test_a_failure_is_shared_too(self):
        group = SingleFlight()
        group.ask("a", "user:42")
        group.ask("b", "user:42")
        told = group.land("user:42", outcome="timeout")
        assert told == ["a", "b"]
        assert "timeout shared with 2" in group.landed[0]

    def test_the_next_ask_after_landing_flies_fresh(self):
        group = SingleFlight()
        group.ask("a", "user:42")
        group.land("user:42", outcome="row-42")
        assert group.ask("b", "user:42") == "fly"

    def test_landing_the_unflown_is_named(self):
        with pytest.raises(Invalid):
            SingleFlight().land("ghost", outcome="x")


class TestTheStampede:
    def test_the_expiry_stampede_costs_one_trip(self):
        group = SingleFlight()
        group.ask("caller-0", "hot-key")
        for number in range(1, 100):
            group.ask(f"caller-{number}", "hot-key")
        assert group.trips_flown == 1
        assert group.trips_saved == 99
        assert "99% of questions answered by sharing" in group.meter()

    def test_an_idle_meter_says_so(self):
        assert SingleFlight().meter() == "no questions asked"
