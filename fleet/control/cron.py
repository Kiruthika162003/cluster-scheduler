"""Cron: schedules fire on time, and the missed-window policy is the design.

A schedule names the ticks a job should launch. The keeper was asleep,
the cluster was down, three windows passed: what now is the entire
difference between cron implementations. Skip forgets them, catch-up
runs them all back to back, and one-shot runs a single make-up because
most jobs are idempotent over their period. The policy is per schedule,
because the backup wants catch-up and the cache warmer wants skip, and
a global default is always wrong for half the fleet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.control.jobs import JobSpec
from fleet.errors import Invalid


@dataclass(frozen=True)
class Schedule:
    name: str
    every: int
    job: JobSpec
    missed_policy: str = "one-shot"

    def __post_init__(self) -> None:
        if self.every < 1:
            raise Invalid(f"{self.name}: every must be positive")
        if self.missed_policy not in ("skip", "catch-up", "one-shot"):
            raise Invalid(f"{self.name}: unknown policy {self.missed_policy}")

    def due_at(self, tick: int) -> bool:
        return tick % self.every == 0


@dataclass
class Cron:
    schedules: list[Schedule] = field(default_factory=list)
    last_seen: dict[str, int] = field(default_factory=dict)
    launches: list[tuple[int, str]] = field(default_factory=list)
    skipped: int = 0

    def tick(self, now: int) -> list[str]:
        fired = []
        for schedule in self.schedules:
            last = self.last_seen.get(schedule.name, -1)
            missed = [
                tick
                for tick in range(last + 1, now)
                if schedule.due_at(tick)
            ]
            due_now = schedule.due_at(now)
            to_run: list[int] = []
            if missed:
                if schedule.missed_policy == "catch-up":
                    to_run.extend(missed)
                elif schedule.missed_policy == "one-shot":
                    to_run.append(missed[-1])
                    self.skipped += len(missed) - 1
                else:
                    self.skipped += len(missed)
            if due_now:
                to_run.append(now)
            for when in to_run:
                self.launches.append((when, schedule.name))
                fired.append(f"{schedule.name}@{when}")
            self.last_seen[schedule.name] = now
        return fired
