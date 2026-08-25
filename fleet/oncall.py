"""The on-call brief: one page that answers the 2am questions in order.

What is broken, what changed, what is the cluster doing, and is the
system still keeping its promises. The brief composes the pages that
already exist, in that order, because the on-call reader triages top
to bottom and every section they do not need to read is time returned
to them. A quiet brief says so in one line per section; quiet is a
finding, not an absence.
"""

from __future__ import annotations

import io

from fleet.audit import Journal
from fleet.conformance import Conformance
from fleet.store import Store
from fleet.verify import violations
from fleet.whatchanged import what_changed


def brief(
    store: Store,
    journal: Journal,
    since: int,
    running: int,
    serving: int,
) -> str:
    out = io.StringIO()
    out.write("on-call brief\n")
    out.write("=" * 40 + "\n")

    broken = violations(store)
    out.write("broken:\n")
    if broken:
        for sentence in broken:
            out.write(f"  {sentence}\n")
    else:
        out.write("  nothing; invariants hold\n")

    out.write("changed:\n")
    window = what_changed(store, since)
    out.write(f"  {window.sentence()}\n")

    out.write("doing:\n")
    out.write(f"  {running} running, {serving} serving\n")
    ghost_gap = running - serving
    if ghost_gap:
        out.write(f"  {ghost_gap} running on nodes that cannot serve them\n")

    recent = journal.decisions[-5:]
    out.write("recent decisions:\n")
    if recent:
        for decision in recent:
            out.write(f"  {decision.line()}\n")
    else:
        out.write("  none recorded\n")

    suite = Conformance()
    suite.run()
    failing = suite.failing()
    out.write("promises:\n")
    if failing:
        for check in failing:
            out.write(f"  BROKEN {check.name}: {check.promise}\n")
    else:
        out.write(f"  all {len(suite.results)} conformance checks hold\n")
    return out.getvalue()
