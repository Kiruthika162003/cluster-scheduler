"""Address allocation: reuse too fast and yesterday's mail arrives today.

Endpoints get addresses from a finite pool. Releasing an address does
not silence the network: messages already in flight toward it arrive
for ticks afterwards, and an address reissued inside that window hands
another tenant's traffic to a stranger. The allocator's cooldown holds
released addresses out of circulation for the flight time, priced in
pool headroom: the same pool serves fewer live tenants because some of
it is always cooling. Misdelivery or headroom; the window decides.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass
class Allocator:
    pool_size: int
    cooldown: int
    free: list[int] = field(default_factory=list)
    cooling: dict[int, int] = field(default_factory=dict)
    held: dict[int, str] = field(default_factory=dict)
    denied_empty: int = 0

    def __post_init__(self) -> None:
        if not self.free and not self.held:
            self.free = list(range(self.pool_size))

    def allocate(self, tenant: str, now: int) -> int | None:
        for address, until in sorted(self.cooling.items()):
            if until <= now:
                self.free.append(address)
                del self.cooling[address]
        if not self.free:
            self.denied_empty += 1
            return None
        address = self.free.pop(0)
        self.held[address] = tenant
        return address

    def release(self, address: int, now: int) -> None:
        if address not in self.held:
            raise Invalid(f"address {address} is not held")
        del self.held[address]
        if self.cooldown:
            self.cooling[address] = now + self.cooldown
        else:
            self.free.append(address)


@dataclass
class FlightModel:
    """Messages sent toward an address arrive flight_time ticks later."""

    flight_time: int
    in_flight: list[tuple[int, int, str]] = field(default_factory=list)
    misdelivered: list[str] = field(default_factory=list)
    delivered: int = 0

    def send(self, address: int, sender: str, now: int) -> None:
        self.in_flight.append((now + self.flight_time, address, sender))

    def deliver(self, allocator: Allocator, now: int) -> None:
        still = []
        for arrives, address, sender in self.in_flight:
            if arrives > now:
                still.append((arrives, address, sender))
                continue
            owner = allocator.held.get(address)
            if owner is None:
                continue
            if owner != sender:
                self.misdelivered.append(
                    f"{sender}'s message arrived at {owner} on {address}"
                )
            else:
                self.delivered += 1
        self.in_flight = still
