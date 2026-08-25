"""One object's life on one page: events and decisions, merged and told.

The store's events say what happened to the object; the journal says
who did it and why. The timeline merges both streams by tick, tells
each entry in a sentence, and closes with the phase history verdict
from the phase machine, so the page ends by saying whether this life
was even legal. It is the page an operator wants when one task is
weird and nothing else is.
"""

from __future__ import annotations

import io

from fleet.audit import Journal
from fleet.phases import check_history
from fleet.store import Store


def phase_history(journal: Journal, store: Store, name: str) -> list[str]:
    """Best-effort life from the journal's verbs plus the current phase."""
    life = ["Pending"]
    for decision in journal.about(name):
        if decision.verb == "bind":
            life.append("Bound")
        elif decision.verb in ("displace", "evict"):
            life.append("Evicted")
            life.append("Pending")
    held = store.tasks.get(name)
    if held is not None and held.phase not in (life[-1],):
        life.append(held.phase)
    return life


def timeline(store: Store, journal: Journal, name: str) -> str:
    out = io.StringIO()
    out.write(f"timeline of {name}\n")
    entries: list[tuple[int, str]] = []
    for sequence, event in enumerate(store.events):
        if event.name == name:
            entries.append((sequence, f"store: {event.kind}"))
    for decision in journal.about(name):
        entries.append(
            (decision.tick, f"{decision.actor}: {decision.verb}, {decision.reason}")
        )
    for when, line in sorted(entries, key=lambda held: held[0]):
        out.write(f"  [{when}] {line}\n")
    if not entries:
        out.write("  nothing recorded\n")
    held = store.tasks.get(name)
    if held is not None:
        out.write(f"  now: {held.phase}")
        out.write(f" on {held.node}\n" if held.node else "\n")
    else:
        out.write("  now: gone\n")
    life = phase_history(journal, store, name)
    illegal = check_history(life)
    if illegal is None:
        out.write(f"  life was legal: {' -> '.join(life)}\n")
    else:
        out.write(f"  ILLEGAL step {illegal} in {' -> '.join(life)}\n")
    return out.getvalue()
