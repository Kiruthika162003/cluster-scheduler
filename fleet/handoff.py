"""The shift handoff: what the next on-call inherits, on one page.

Standing cordons with their reasons and ages, live notes, anything
stuck leaving, the starving tail of the queue, and the last few
decisions. The page is written for the person who was not here today,
which is the discipline: no pronouns without antecedents, no "the
usual issue", every line self-contained enough to act on at 3am
without calling the author.
"""

from __future__ import annotations

import io

from fleet.audit import Journal
from fleet.control.finalizers import Departures
from fleet.cordonttl import CordonLeases
from fleet.notes import Noteboard
from fleet.queuestats import snapshot
from fleet.sched.queue import SchedulingQueue


def handoff(
    now: int,
    leases: CordonLeases,
    notes: Noteboard,
    departures: Departures,
    queue: SchedulingQueue,
    journal: Journal,
) -> str:
    out = io.StringIO()
    out.write(f"shift handoff at {now}\n")
    out.write("=" * 40 + "\n")

    out.write("standing cordons:\n")
    standing = leases.standing(now)
    if standing:
        for line in standing:
            out.write(f"  {line}\n")
    else:
        out.write("  none\n")

    out.write("live notes:\n")
    live = notes.live_notes(now)
    if live:
        for note in live:
            out.write(f"  {note.line()}\n")
    else:
        out.write("  none\n")

    out.write("stuck leaving:\n")
    stuck = departures.stuck(now, patience=10)
    if stuck:
        for line in stuck:
            out.write(f"  {line}\n")
    else:
        out.write("  nothing\n")

    out.write("the queue:\n")
    stats = snapshot(queue)
    out.write("  " + stats.render().replace("\n", "\n  ").rstrip() + "\n")

    out.write("recent decisions:\n")
    recent = journal.decisions[-3:]
    if recent:
        for decision in recent:
            out.write(f"  {decision.line()}\n")
    else:
        out.write("  none\n")
    return out.getvalue()
