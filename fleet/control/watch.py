"""Informers: a controller's private cache, fed by events, honest on resume.

The event log carries names, not payloads, so replaying an add for an
object that was later removed must read absence gracefully: the remove
event that follows keeps the cache right, and the add of a ghost applies
as nothing.

A controller that lists the world on every pass does quadratic work; one
that trusts a stale cache does wrong work. The informer replays the
store's events from its cursor into a local index and hands the
controller a view that is exactly as fresh as the last replay. A crashed
informer is just an informer with an older cursor: resume is replay, and
the trial-grade property is that replay from zero and replay in pieces
build identical caches.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.store import Store


@dataclass
class Informer:
    cursor: int = 0
    known_tasks: dict[str, str] = field(default_factory=dict)
    known_nodes: set[str] = field(default_factory=set)
    replays: int = 0

    def refresh(self, store: Store) -> int:
        """Replay unseen events; returns how many were applied."""
        applied = 0
        for event in store.since(self.cursor):
            if event.kind in ("task-added", "task-updated"):
                held = store.tasks.get(event.name)
                if held is not None:
                    self.known_tasks[event.name] = held.phase
            elif event.kind == "task-removed":
                self.known_tasks.pop(event.name, None)
            elif event.kind == "node-added":
                self.known_nodes.add(event.name)
            elif event.kind == "node-removed":
                self.known_nodes.discard(event.name)
            self.cursor = event.sequence + 1
            applied += 1
        self.replays += 1
        return applied

    def phase_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for phase in self.known_tasks.values():
            counts[phase] = counts.get(phase, 0) + 1
        return counts

    def agrees_with(self, store: Store) -> bool:
        truth = {name: task.phase for name, task in store.tasks.items()}
        return self.known_tasks == truth and self.known_nodes == set(store.nodes)
