"""Crash loops: backoff turns a restart storm into a restart schedule.

A task that dies on start and restarts immediately will do nothing
but die, as fast as the machine allows. The tracker doubles the wait
after every crash up to a cap, resets it after a stretch of healthy
running, and stamps the verdict CrashLoopBackOff once the streak
crosses the threshold, because the owner needs the name before the
graph. Restart storms are a fleet symptom, not a task one: when many
tasks enter backoff inside a short window the storm detector points
at the shared cause, node, image, or config push, by counting what
the crashers have in common. The arithmetic that matters: an
immediate-restart loop burns a restart per tick, 1000 in 1000 ticks;
the backoff curve spends six restarts reaching its 64-tick cap and a
permanently broken task costs 20 restarts in the same 1000 ticks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BACKOFF_BASE = 2
BACKOFF_CAP = 64
LOOP_THRESHOLD = 5
HEALTHY_RESET = 30
STORM_WINDOW = 10
STORM_COUNT = 3


@dataclass
class CrashRecord:
    crashes: int = 0
    streak: int = 0
    last_crash: int | None = None
    wait_until: int = 0
    healthy_since: int | None = None


@dataclass
class CrashTracker:
    records: dict[str, CrashRecord] = field(default_factory=dict)
    context: dict[str, dict[str, str]] = field(default_factory=dict)

    def _record(self, task: str) -> CrashRecord:
        return self.records.setdefault(task, CrashRecord())

    def register(self, task: str, **facts: str) -> None:
        self.context[task] = dict(facts)

    def crashed(self, task: str, now: int) -> int:
        record = self._record(task)
        if (
            record.healthy_since is not None
            and now - record.healthy_since >= HEALTHY_RESET
        ):
            record.streak = 0
        record.crashes += 1
        record.streak += 1
        record.last_crash = now
        record.healthy_since = None
        wait = min(BACKOFF_CAP, BACKOFF_BASE**record.streak)
        record.wait_until = now + wait
        return wait

    def started(self, task: str, now: int) -> None:
        record = self._record(task)
        record.healthy_since = now

    def may_restart(self, task: str, now: int) -> bool:
        return now >= self._record(task).wait_until

    def verdict(self, task: str) -> str:
        record = self._record(task)
        if record.streak >= LOOP_THRESHOLD:
            return "CrashLoopBackOff"
        if record.streak > 0:
            return f"crashing ({record.streak} in a row)"
        return "healthy"

    def storm(self, now: int) -> str | None:
        stormers = [
            task
            for task, record in self.records.items()
            if record.streak >= 2
            and record.last_crash is not None
            and now - record.last_crash <= STORM_WINDOW
        ]
        if len(stormers) < STORM_COUNT:
            return None
        common: dict[str, dict[str, int]] = {}
        for task in stormers:
            for key, value in self.context.get(task, {}).items():
                common.setdefault(key, {})[value] = (
                    common.get(key, {}).get(value, 0) + 1
                )
        best_key = best_value = None
        best_count = 0
        for key in sorted(common):
            for value in sorted(common[key]):
                if common[key][value] > best_count:
                    best_key, best_value = key, value
                    best_count = common[key][value]
        if best_count >= len(stormers):
            return (
                f"storm: {len(stormers)} tasks crashing, all sharing "
                f"{best_key}={best_value}"
            )
        return (
            f"storm: {len(stormers)} tasks crashing, no single shared "
            f"cause; check the fleet, not one task"
        )
