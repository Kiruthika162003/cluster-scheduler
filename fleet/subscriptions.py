"""Subscriptions: watch a slice of the world and resume without gaps.

A subscription is a cursor plus a filter: task events whose subject
matches a selector, node events, or everything. Delivery is pull, the
subscriber owns its cursor, and the resume contract is exact: reading
from a saved cursor yields precisely the events after it, no gaps and
no repeats, which is what lets a subscriber crash, restore its cursor,
and trust its own history. The filter runs on the store's current
object, so a subscription to app=web sees the add of a web task and
never the add of anything else.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleet.selector import Clause, matches, parse
from fleet.store import Event, Store


@dataclass
class Subscription:
    name: str
    kind_prefix: str | None = None
    selector: tuple[Clause, ...] | None = None
    cursor: int = 0
    delivered: int = 0

    def _wants(self, store: Store, event: Event) -> bool:
        if self.kind_prefix is not None and not event.kind.startswith(
            self.kind_prefix
        ):
            return False
        if self.selector is None:
            return True
        held = store.tasks.get(event.name)
        if held is None:
            return False
        return matches(self.selector, held.spec.label_map())

    def pull(self, store: Store) -> list[Event]:
        fresh = []
        for event in store.since(self.cursor):
            self.cursor = event.sequence + 1
            if self._wants(store, event):
                fresh.append(event)
        self.delivered += len(fresh)
        return fresh


def subscribe(
    name: str,
    kind_prefix: str | None = None,
    selector_text: str | None = None,
) -> Subscription:
    return Subscription(
        name=name,
        kind_prefix=kind_prefix,
        selector=parse(selector_text) if selector_text else None,
    )
