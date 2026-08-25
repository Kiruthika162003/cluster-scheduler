from __future__ import annotations

import pytest

from fleet.allocator import Allocator, FlightModel
from fleet.errors import Invalid


class TestAllocator:
    def test_addresses_issue_in_order(self):
        allocator = Allocator(pool_size=3, cooldown=0)
        assert allocator.allocate("a", now=0) == 0
        assert allocator.allocate("b", now=0) == 1

    def test_an_empty_pool_denies_and_counts(self):
        allocator = Allocator(pool_size=1, cooldown=0)
        allocator.allocate("a", now=0)
        assert allocator.allocate("b", now=0) is None
        assert allocator.denied_empty == 1

    def test_release_without_cooldown_reissues_immediately(self):
        allocator = Allocator(pool_size=1, cooldown=0)
        allocator.allocate("a", now=0)
        allocator.release(0, now=0)
        assert allocator.allocate("b", now=0) == 0

    def test_a_cooling_address_is_withheld(self):
        allocator = Allocator(pool_size=1, cooldown=5)
        allocator.allocate("a", now=0)
        allocator.release(0, now=0)
        assert allocator.allocate("b", now=3) is None
        assert allocator.allocate("b", now=5) == 0

    def test_releasing_an_unheld_address_is_refused(self):
        with pytest.raises(Invalid):
            Allocator(pool_size=1, cooldown=0).release(0, now=0)


class TestFlight:
    def test_a_message_to_its_owner_delivers(self):
        allocator = Allocator(pool_size=1, cooldown=0)
        allocator.allocate("a", now=0)
        flight = FlightModel(flight_time=2)
        flight.send(0, "a", now=0)
        flight.deliver(allocator, now=2)
        assert flight.delivered == 1 and flight.misdelivered == []

    def test_a_message_to_a_freed_address_drops_silently(self):
        allocator = Allocator(pool_size=1, cooldown=0)
        allocator.allocate("a", now=0)
        flight = FlightModel(flight_time=2)
        flight.send(0, "a", now=0)
        allocator.release(0, now=1)
        flight.deliver(allocator, now=2)
        assert flight.delivered == 0 and flight.misdelivered == []

    def test_a_message_to_a_reissued_address_misdelivers(self):
        allocator = Allocator(pool_size=1, cooldown=0)
        allocator.allocate("a", now=0)
        flight = FlightModel(flight_time=2)
        flight.send(0, "a", now=0)
        allocator.release(0, now=1)
        allocator.allocate("b", now=1)
        flight.deliver(allocator, now=2)
        assert flight.misdelivered == ["a's message arrived at b on 0"]

    def test_undelivered_messages_wait_in_flight(self):
        allocator = Allocator(pool_size=1, cooldown=0)
        allocator.allocate("a", now=0)
        flight = FlightModel(flight_time=5)
        flight.send(0, "a", now=0)
        flight.deliver(allocator, now=2)
        assert len(flight.in_flight) == 1
