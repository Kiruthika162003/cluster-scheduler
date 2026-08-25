from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.reservations import Broker
from fleet.store import Store


def roomy_store() -> Store:
    store = Store()
    for number in range(2):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    return store


class TestBooking:
    def test_a_booking_inside_capacity_lands(self):
        broker = Broker()
        booking = broker.book(roomy_store(), "batch", 1500, starts=60, ends=90)
        assert booking.cpu == 1500

    def test_a_backwards_window_is_refused(self):
        with pytest.raises(Invalid):
            Broker().book(roomy_store(), "batch", 100, starts=90, ends=60)

    def test_overbooking_the_same_window_is_refused_with_numbers(self):
        store = roomy_store()
        broker = Broker()
        broker.book(store, "first", 1500, starts=60, ends=90)
        with pytest.raises(Invalid) as caught:
            broker.book(store, "second", 800, starts=70, ends=80)
        assert "only 500m unbooked" in str(caught.value)

    def test_disjoint_windows_share_capacity(self):
        store = roomy_store()
        broker = Broker()
        broker.book(store, "morning", 1500, starts=10, ends=20)
        broker.book(store, "evening", 1500, starts=60, ends=90)
        assert len(broker.bookings) == 2

    def test_running_work_shrinks_what_is_bookable(self):
        store = roomy_store()
        tenant = Task(spec=TaskSpec(name="t", needs=Resources(cpu=800, memory=100)))
        tenant.bound_to("n0")
        store.add_task(tenant)
        broker = Broker()
        with pytest.raises(Invalid):
            broker.book(store, "batch", 1500, starts=60, ends=90)

    def test_release_frees_the_name_and_the_capacity(self):
        store = roomy_store()
        broker = Broker()
        broker.book(store, "batch", 1500, starts=60, ends=90)
        broker.release("batch")
        broker.book(store, "batch", 1500, starts=60, ends=90)


class TestScaleGate:
    def test_a_scale_that_eats_a_future_booking_is_refused(self):
        store = roomy_store()
        broker = Broker()
        broker.book(store, "batch", 1500, starts=60, ends=90)
        allowed, why = broker.may_scale(store, cpu=800, now=10)
        assert not allowed
        assert "raw free would have said 2000m" in why

    def test_a_modest_scale_clears_the_bookings(self):
        store = roomy_store()
        broker = Broker()
        broker.book(store, "batch", 1500, starts=60, ends=90)
        allowed, _ = broker.may_scale(store, cpu=400, now=10)
        assert allowed

    def test_without_bookings_the_gate_is_wide_open(self):
        allowed, why = Broker().may_scale(roomy_store(), cpu=1900, now=0)
        assert allowed and "2000m truly free" in why
