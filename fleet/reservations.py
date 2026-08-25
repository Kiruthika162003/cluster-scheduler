"""Reservations: the six o'clock batch owns its capacity at noon.

A reservation books capacity for a window in the future. The broker
answers the only two questions that matter: how much headroom is
really free right now, meaning free minus every booking that overlaps
now, and whether a new booking fits inside the future it names. A
scale-up that consults raw free capacity eats the evening batch's
booking at noon and the batch pages at six; a scale-up that consults
the broker is refused at noon, which is the cheaper page by hours.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.objects import free
from fleet.store import Store


@dataclass(frozen=True)
class Booking:
    name: str
    cpu: int
    starts: int
    ends: int

    def overlaps(self, tick: int) -> bool:
        return self.starts <= tick < self.ends

    def intersects(self, starts: int, ends: int) -> bool:
        return self.starts < ends and starts < self.ends


@dataclass
class Broker:
    bookings: dict[str, Booking] = field(default_factory=dict)
    refusals: list[str] = field(default_factory=list)

    def _fleet_free(self, store: Store) -> int:
        active = store.active_tasks()
        total = 0
        for node in store.nodes.values():
            if node.ready and node.schedulable:
                total += free(node, active).cpu
        return total

    def reserved_at(self, tick: int) -> int:
        return sum(
            booking.cpu
            for booking in self.bookings.values()
            if booking.overlaps(tick)
        )

    def reserved_over(self, starts: int, ends: int) -> int:
        return sum(
            booking.cpu
            for booking in self.bookings.values()
            if booking.intersects(starts, ends)
        )

    def headroom(self, store: Store, now: int, horizon: int = 0) -> int:
        window_end = now + max(horizon, 1)
        return self._fleet_free(store) - self.reserved_over(now, window_end)

    def book(
        self, store: Store, name: str, cpu: int, starts: int, ends: int
    ) -> Booking:
        if ends <= starts:
            raise Invalid(f"{name}: the window ends before it starts")
        if name in self.bookings:
            raise Invalid(f"{name} is already booked")
        available = self._fleet_free(store) - self.reserved_over(starts, ends)
        if cpu > available:
            refusal = (
                f"{name} wants {cpu}m over [{starts},{ends}), "
                f"only {available}m unbooked"
            )
            self.refusals.append(refusal)
            raise Invalid(refusal)
        booking = Booking(name=name, cpu=cpu, starts=starts, ends=ends)
        self.bookings[name] = booking
        return booking

    def release(self, name: str) -> None:
        if name not in self.bookings:
            raise Invalid(f"{name} holds no booking")
        del self.bookings[name]

    def may_scale(self, store: Store, cpu: int, now: int) -> tuple[bool, str]:
        """A persistent scale-up occupies the future, so it must clear
        every booking from now on, not just the ones overlapping now."""
        room = self._fleet_free(store) - self.reserved_over(now, 10**9)
        if cpu <= room:
            return True, f"{room}m truly free"
        return False, (
            f"only {room}m after bookings; raw free would have said "
            f"{self._fleet_free(store)}m"
        )
