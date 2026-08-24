"""Optimistic concurrency for controllers: read, decide, write, maybe again.

Two controllers editing one object is Tuesday. The retry loop reads the
object fresh, applies the caller's edit, and writes with the generation
it read; a Conflict means somebody moved first, so the loop reads again
and re-decides against the new truth rather than replaying a stale
intention. The attempt cap turns a livelock into an error with a count
attached instead of a spinning silence.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fleet.errors import Conflict
from fleet.objects import Task
from fleet.store import Store


@dataclass
class RetryLoop:
    attempts_allowed: int = 5
    attempts_spent: int = 0
    conflicts_absorbed: int = 0

    def edit(self, store: Store, name: str, change: Callable[[Task], None]) -> Task:
        last: Conflict | None = None
        for _ in range(self.attempts_allowed):
            self.attempts_spent += 1
            held = store.get_task(name)
            generation = held.generation
            change(held)
            try:
                store.update_task(held, read_generation=generation)
            except Conflict as refused:
                self.conflicts_absorbed += 1
                last = refused
                continue
            return held
        raise Conflict(
            f"{name}: {self.attempts_allowed} attempts, "
            f"{self.conflicts_absorbed} conflicts: {last}"
        )
