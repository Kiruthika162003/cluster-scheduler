"""Bulkheads: one drowning dependency must not pull the ship under.

A service that calls three backends through one thread pool sinks
whole when the slowest backend stalls: every worker ends up parked
in the same wait. Bulkheads give each dependency its own bounded
pool plus a small bounded queue; when both fill, calls to that
dependency are refused immediately while every other compartment
keeps working. The refusal is the feature, not the failure: a fast
no from a full compartment costs microseconds, while the sunk
alternative costs every request in the ship. The water line report
shows each compartment's occupancy so the operator can see which
dependency is drowning before the graphs do.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass
class Compartment:
    name: str
    pool_size: int
    queue_size: int
    in_flight: dict[str, int] = field(default_factory=dict)
    queued: list[tuple[str, int]] = field(default_factory=list)
    refused: int = 0
    completed: int = 0

    def __post_init__(self) -> None:
        if self.pool_size <= 0 or self.queue_size < 0:
            raise Invalid("a compartment needs a positive pool")

    def submit(self, call: str, now: int, takes: int) -> str:
        if len(self.in_flight) < self.pool_size:
            self.in_flight[call] = now + takes
            return "running"
        if len(self.queued) < self.queue_size:
            self.queued.append((call, takes))
            return "queued"
        self.refused += 1
        return f"refused: {self.name} is full"

    def tick(self, now: int) -> list[str]:
        done = sorted(
            call
            for call, finishes in self.in_flight.items()
            if finishes <= now
        )
        for call in done:
            del self.in_flight[call]
            self.completed += 1
        while self.queued and len(self.in_flight) < self.pool_size:
            call, takes = self.queued.pop(0)
            self.in_flight[call] = now + takes
        return done

    def water_line(self) -> str:
        return (
            f"{self.name}: {len(self.in_flight)}/{self.pool_size} running, "
            f"{len(self.queued)}/{self.queue_size} queued, "
            f"{self.refused} refused"
        )


@dataclass
class Ship:
    compartments: dict[str, Compartment] = field(default_factory=dict)

    def partition(self, name: str, pool_size: int, queue_size: int) -> Compartment:
        if name in self.compartments:
            raise Invalid(f"{name} is already partitioned")
        compartment = Compartment(
            name=name, pool_size=pool_size, queue_size=queue_size
        )
        self.compartments[name] = compartment
        return compartment

    def submit(self, dependency: str, call: str, now: int, takes: int) -> str:
        if dependency not in self.compartments:
            raise Invalid(f"no compartment for {dependency}")
        return self.compartments[dependency].submit(call, now, takes)

    def tick(self, now: int) -> None:
        for compartment in self.compartments.values():
            compartment.tick(now)

    def drowning(self) -> list[str]:
        return sorted(
            name
            for name, compartment in self.compartments.items()
            if len(compartment.in_flight) >= compartment.pool_size
            and len(compartment.queued) >= compartment.queue_size
        )

    def report(self) -> str:
        lines = [f"{len(self.drowning())} compartment(s) at the water line"]
        for name in sorted(self.compartments):
            lines.append("  " + self.compartments[name].water_line())
        return "\n".join(lines)
