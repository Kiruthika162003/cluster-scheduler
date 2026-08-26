"""Single flight: a hundred identical questions deserve one trip.

When a cache entry expires, every waiting request charges the
backend with the same question at once, and the backend answers the
same thing a hundred times while sweating. Single flight collapses
them: the first caller becomes the leader and flies; everyone else
with the same key waits on the leader's answer and shares it. The
sharing window ends when the flight lands, so answers are never
stale beyond one flight time, and a failed flight is shared too,
because a hundred callers re-asking after a failure is the stampede
wearing a different hat. The meter reports trips saved, which for a
hot key during an expiry is nearly everything.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass
class Flight:
    key: str
    leader: str
    passengers: list[str] = field(default_factory=list)
    outcome: str | None = None


@dataclass
class SingleFlight:
    flights: dict[str, Flight] = field(default_factory=dict)
    trips_flown: int = 0
    trips_saved: int = 0
    landed: list[str] = field(default_factory=list)

    def ask(self, caller: str, key: str) -> str:
        flight = self.flights.get(key)
        if flight is None:
            self.flights[key] = Flight(key=key, leader=caller)
            self.trips_flown += 1
            return "fly"
        if caller == flight.leader or caller in flight.passengers:
            raise Invalid(f"{caller} is already aboard {key}")
        flight.passengers.append(caller)
        self.trips_saved += 1
        return f"wait: {flight.leader} is flying {key}"

    def land(self, key: str, outcome: str) -> list[str]:
        flight = self.flights.pop(key, None)
        if flight is None:
            raise Invalid(f"no flight for {key}")
        flight.outcome = outcome
        told = [flight.leader, *flight.passengers]
        self.landed.append(
            f"{key}: {outcome} shared with {len(told)} caller(s)"
        )
        return told

    def in_flight(self) -> list[str]:
        return sorted(self.flights)

    def meter(self) -> str:
        total = self.trips_flown + self.trips_saved
        if total == 0:
            return "no questions asked"
        share = self.trips_saved / total
        return (
            f"{self.trips_flown} trips flown, {self.trips_saved} saved "
            f"({share:.0%} of questions answered by sharing)"
        )
