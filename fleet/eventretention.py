"""Event retention: truncation never strands a subscriber mid-resume.

The event log grows forever unless someone truncates it, and the
truncation that breaks a subscriber's cursor converts a crash-safe
consumer into a silently gapped one, the worst outcome in the room.
The retention keeper tracks registered cursors and refuses to compact
past the laggard, naming it, so the operator's choice is explicit:
wait for the slow consumer, or expel it and compact, but never both
halves of neither.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.store import Store


@dataclass
class RetentionKeeper:
    cursors: dict[str, int] = field(default_factory=dict)
    compacted_below: int = 0
    expelled: list[str] = field(default_factory=list)

    def register(self, subscriber: str, cursor: int) -> None:
        self.cursors[subscriber] = cursor

    def advance(self, subscriber: str, cursor: int) -> None:
        if subscriber not in self.cursors:
            raise Invalid(f"{subscriber} is not registered")
        self.cursors[subscriber] = cursor

    def laggard(self) -> tuple[str, int] | None:
        if not self.cursors:
            return None
        subscriber = min(self.cursors, key=lambda name: (self.cursors[name], name))
        return subscriber, self.cursors[subscriber]

    def compact(self, store: Store, keep_from: int) -> int:
        held = self.laggard()
        if held is not None and held[1] < keep_from:
            raise Invalid(
                f"compacting to {keep_from} would strand {held[0]} "
                f"at cursor {held[1]}"
            )
        if keep_from <= self.compacted_below:
            return 0
        removable = [
            event for event in store.events if event.sequence < keep_from
        ]
        store.events = [
            event for event in store.events if event.sequence >= keep_from
        ]
        self.compacted_below = keep_from
        return len(removable)

    def expel(self, subscriber: str) -> None:
        if subscriber not in self.cursors:
            raise Invalid(f"{subscriber} is not registered")
        del self.cursors[subscriber]
        self.expelled.append(subscriber)
