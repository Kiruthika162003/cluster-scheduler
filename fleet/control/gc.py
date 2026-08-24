"""Task garbage collection: finished history is kept, bounded, then gone.

Succeeded and failed tasks are records worth reading until they are
noise worth deleting. The collector keeps each kind under a cap and
everything under a time-to-live, deleting oldest-first, and it never
touches anything active. The caps are per kind because one crashlooping
deployment can otherwise flush every success out of the history.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.store import Store


@dataclass
class Collector:
    keep_succeeded: int = 20
    keep_failed: int = 50
    ttl: int = 200
    finished_at: dict[str, int] = field(default_factory=dict)
    collected: int = 0

    def note_finished(self, store: Store, now: int) -> None:
        for task in store.tasks.values():
            name = task.spec.name
            if task.phase in ("Succeeded", "Failed") and name not in self.finished_at:
                self.finished_at[name] = now

    def sweep(self, store: Store, now: int) -> int:
        self.note_finished(store, now)
        removed = 0
        for name, when in list(self.finished_at.items()):
            if name not in store.tasks:
                del self.finished_at[name]
                continue
            if now - when >= self.ttl:
                store.remove_task(name)
                del self.finished_at[name]
                removed += 1
        for phase, cap in (("Succeeded", self.keep_succeeded), ("Failed", self.keep_failed)):
            held = sorted(
                (
                    task.spec.name
                    for task in store.tasks.values()
                    if task.phase == phase
                ),
                key=lambda name: (self.finished_at.get(name, 0), name),
            )
            while len(held) > cap:
                victim = held.pop(0)
                store.remove_task(victim)
                self.finished_at.pop(victim, None)
                removed += 1
        self.collected += removed
        return removed
