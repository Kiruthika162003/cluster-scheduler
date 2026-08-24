"""What changed since tick N: the event log read as an operator's answer.

The store's events already hold the whole history; this page folds a
window of them into the sentence an operator actually asks for. Churn
per object collapses to its net effect: an object added and removed
inside the window nets to nothing but is reported as churn, because
flapping that cancels out is still flapping, and the page that hides it
hides the most interesting thing that happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.store import Store


@dataclass(frozen=True)
class Change:
    name: str
    kind: str
    net: str
    touches: int


@dataclass
class Window:
    since: int
    changes: list[Change] = field(default_factory=list)
    churned: list[str] = field(default_factory=list)

    def sentence(self) -> str:
        if not self.changes and not self.churned:
            return f"nothing changed since {self.since}"
        parts = []
        for change in self.changes:
            parts.append(f"{change.net} {change.kind}/{change.name}")
        for name in self.churned:
            parts.append(f"churned {name}")
        return "; ".join(parts)


def what_changed(store: Store, since: int) -> Window:
    touches: dict[str, list[str]] = {}
    kinds: dict[str, str] = {}
    for event in store.since(since):
        kind, verb = event.kind.rsplit("-", 1)
        touches.setdefault(event.name, []).append(verb)
        kinds[event.name] = kind
    window = Window(since=since)
    for name in sorted(touches):
        verbs = touches[name]
        added = "added" in verbs
        removed = "removed" in verbs
        if added and removed:
            window.churned.append(f"{kinds[name]}/{name}")
            continue
        if added:
            net = "created"
        elif removed:
            net = "deleted"
        else:
            net = "updated"
        window.changes.append(
            Change(name=name, kind=kinds[name], net=net, touches=len(verbs))
        )
    return window
