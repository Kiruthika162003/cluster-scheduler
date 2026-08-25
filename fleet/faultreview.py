"""The incident review, drafted by the cluster that lived it.

The review page takes the incident window and composes what the
machines already recorded: the journal's decisions inside the window,
the store's churn, the pager's noise budget, and the invariant state
at close. The draft is not the review; it is the part of the review
nobody should have to reconstruct from memory, laid out in the order
reviews are read: what happened, who did what, what it cost, and
whether the cluster is whole.
"""

from __future__ import annotations

import io

from fleet.alerts import Pager
from fleet.audit import Journal
from fleet.store import Store
from fleet.verify import violations
from fleet.whatchanged import what_changed


def review(
    store: Store,
    journal: Journal,
    pager: Pager,
    window_start: int,
    window_end: int,
    events_cursor: int,
) -> str:
    out = io.StringIO()
    out.write(f"incident review: ticks {window_start} to {window_end}\n")
    out.write("=" * 44 + "\n")

    out.write("what changed:\n")
    window = what_changed(store, events_cursor)
    out.write(f"  {window.sentence()}\n")

    out.write("who did what:\n")
    inside = [
        decision
        for decision in journal.decisions
        if window_start <= decision.tick <= window_end
    ]
    if inside:
        for decision in inside[:12]:
            out.write(f"  {decision.line()}\n")
        if len(inside) > 12:
            out.write(f"  and {len(inside) - 12} more decisions\n")
    else:
        out.write("  nothing recorded in the window\n")

    out.write("what it cost the pager:\n")
    out.write(
        f"  {len(pager.pages)} pages delivered, {pager.folded} folded\n"
    )

    out.write("is the cluster whole:\n")
    broken = violations(store)
    if broken:
        for sentence in broken:
            out.write(f"  NO: {sentence}\n")
    else:
        out.write("  yes; every invariant holds\n")
    return out.getvalue()
