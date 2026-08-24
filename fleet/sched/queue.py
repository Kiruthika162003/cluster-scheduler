"""The scheduling queue: retries with backoff, and starvation made visible.

An unschedulable task should not be retried every tick, and it should
never be forgotten. The queue holds pending work in priority order,
sends refused tasks to a backoff bench that doubles their wait, and
promotes them back when the bench time expires or when the cluster
changes shape, because a new node invalidates every cached refusal.
The starvation counter ages with each pass so a task that waits forever
is a number an operator can alarm on, not a mystery in a listing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BACKOFF_BASE = 2
BACKOFF_CAP = 64


@dataclass
class Waiting:
    name: str
    priority: int
    refusals: int = 0
    benched_until: int = 0
    passes_waited: int = 0


@dataclass
class SchedulingQueue:
    waiting: dict[str, Waiting] = field(default_factory=dict)
    aging_every: int = 0
    cluster_shape: int = 0
    promotions_on_change: int = 0

    def offer(self, name: str, priority: int) -> None:
        if name not in self.waiting:
            self.waiting[name] = Waiting(name=name, priority=priority)

    def forget(self, name: str) -> None:
        self.waiting.pop(name, None)

    def ready(self, now: int) -> list[str]:
        due = [
            held
            for held in self.waiting.values()
            if held.benched_until <= now
        ]
        for held in due:
            held.passes_waited += 1

        def effective(held: Waiting) -> int:
            if not self.aging_every:
                return held.priority
            return held.priority + held.passes_waited // self.aging_every

        return [
            held.name
            for held in sorted(due, key=lambda w: (-effective(w), w.name))
        ]

    def refuse(self, name: str, now: int) -> int:
        held = self.waiting[name]
        held.refusals += 1
        wait = min(BACKOFF_CAP, BACKOFF_BASE**held.refusals)
        held.benched_until = now + wait
        return wait

    def shape_changed(self, now: int) -> int:
        """A new or removed node clears every bench; refusals are stale."""
        promoted = 0
        for held in self.waiting.values():
            if held.benched_until > now:
                held.benched_until = now
                promoted += 1
        self.promotions_on_change += promoted
        return promoted

    def starving(self, passes: int) -> list[str]:
        return sorted(
            held.name
            for held in self.waiting.values()
            if held.passes_waited >= passes
        )
