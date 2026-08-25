"""Scheduling latency: the queue's wait, told in percentiles per band.

Mean wait is a lie twice over: it hides the tail that pages and it
averages the batch tier's patient hours into the critical tier's
milliseconds. The tracker records offer-to-bind per task, buckets by
priority band, and answers with p50, p95, and worst, because those
are the three numbers an SLO can be written against. Unbound tasks
are reported as still-waiting with their age, not dropped, since the
task that never binds is precisely the one the percentile must not
forget.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.sched.classes import class_of


def percentile(sorted_values: list[int], fraction: float) -> int:
    if not sorted_values:
        raise Invalid("no samples")
    index = int(fraction * (len(sorted_values) - 1) + 0.5)
    return sorted_values[index]


@dataclass
class BandLatency:
    finished: list[int] = field(default_factory=list)

    def summary(self) -> dict:
        ordered = sorted(self.finished)
        return {
            "count": len(ordered),
            "p50": percentile(ordered, 0.50),
            "p95": percentile(ordered, 0.95),
            "worst": ordered[-1],
        }


@dataclass
class LatencyTracker:
    offered_at: dict[str, int] = field(default_factory=dict)
    band_by_task: dict[str, str] = field(default_factory=dict)
    bands: dict[str, BandLatency] = field(default_factory=dict)

    def offered(self, name: str, priority: int, now: int) -> None:
        if name in self.offered_at:
            return
        self.offered_at[name] = now
        self.band_by_task[name] = class_of(priority)

    def bound(self, name: str, now: int) -> int:
        if name not in self.offered_at:
            raise Invalid(f"{name} was never offered")
        wait = now - self.offered_at.pop(name)
        band = self.band_by_task.pop(name)
        self.bands.setdefault(band, BandLatency()).finished.append(wait)
        return wait

    def abandoned(self, name: str) -> None:
        self.offered_at.pop(name, None)
        self.band_by_task.pop(name, None)

    def still_waiting(self, now: int) -> list[tuple[str, str, int]]:
        return sorted(
            (
                (name, self.band_by_task[name], now - offered)
                for name, offered in self.offered_at.items()
            ),
            key=lambda row: (-row[2], row[0]),
        )

    def report(self, now: int) -> str:
        lines = []
        for band in sorted(self.bands):
            numbers = self.bands[band].summary()
            lines.append(
                f"{band}: p50={numbers['p50']} p95={numbers['p95']} "
                f"worst={numbers['worst']} over {numbers['count']} binds"
            )
        waiting = self.still_waiting(now)
        if waiting:
            lines.append(f"{len(waiting)} still waiting:")
            for name, band, age in waiting[:5]:
                lines.append(f"  {name} ({band}) has waited {age}")
        return "\n".join(lines) if lines else "no samples yet"
