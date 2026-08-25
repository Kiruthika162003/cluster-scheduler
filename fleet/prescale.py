"""Predictive pre-scaling: the calendar already knows about the nightly batch.

The cron table is a forecast nobody reads: every schedule names a tick
when demand will arrive. The prescaler reads it, adds capacity a
warmup ahead of each firing, and hands back the capacity after. The
comparison against purely reactive scaling is the queue that forms at
the firing: reactive pays the warmup in queued work every single
night, prescale pays a few idle node-ticks instead, and which currency
is dearer is the operator's call, made with both numbers visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.control.cron import Schedule


@dataclass
class Prescaler:
    warmup: int
    hold_after: int = 5
    ordered: list[tuple[int, int]] = field(default_factory=list)

    def plan(self, schedules: list[Schedule], demand_cpu: int, horizon: int) -> None:
        self.ordered = []
        for schedule in schedules:
            tick = 0
            while tick <= horizon:
                if schedule.due_at(tick):
                    start = max(0, tick - self.warmup)
                    self.ordered.append((start, demand_cpu))
                    self.ordered.append(
                        (tick + self.hold_after, -demand_cpu)
                    )
                tick += 1
        self.ordered.sort()

    def capacity_at(self, base: int, tick: int) -> int:
        extra = 0
        for when, delta in self.ordered:
            if when <= tick:
                extra += delta
        return base + max(0, extra)


def queued_work(
    burst_cpu: int,
    burst_at: int,
    horizon: int,
    capacity_of,
) -> int:
    """Work-tick backlog integral when the burst outruns capacity."""
    queued = 0
    backlog = 0
    for tick in range(horizon):
        if tick == burst_at:
            backlog += burst_cpu
        served = min(backlog, capacity_of(tick))
        backlog -= served
        queued += backlog
    return queued
