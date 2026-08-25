"""Cost anomalies: the bill moved, and the page says which team moved it.

Two usage statements, last week and this week, diffed per namespace
with a threshold that separates drift from events. The attribution is
the point: a 40 percent fleet increase is a meeting, but search grew
9x while everyone else held is a conversation with one team, and the
page draws that distinction automatically. New and vanished namespaces
are called out by name, because the bill that appears from nowhere is
the one nobody budgeted.
"""

from __future__ import annotations

import io

from fleet.metering import Meter

THRESHOLD = 0.25


def anomalies(before: Meter, after: Meter) -> list[str]:
    findings = []
    spaces = set(before.cpu_ticks) | set(after.cpu_ticks)
    for space in sorted(spaces):
        old = before.cpu_ticks.get(space, 0)
        new = after.cpu_ticks.get(space, 0)
        if old == 0 and new > 0:
            findings.append(f"{space}: new spend, {new} cpu-ticks from nothing")
            continue
        if new == 0 and old > 0:
            findings.append(f"{space}: spend vanished, was {old}")
            continue
        change = (new - old) / old
        if abs(change) >= THRESHOLD:
            direction = "up" if change > 0 else "down"
            findings.append(
                f"{space}: {direction} {abs(change):.0%}, {old} to {new}"
            )
    return findings


def attribution(before: Meter, after: Meter) -> str:
    total_old = before.total_cpu_ticks()
    total_new = after.total_cpu_ticks()
    growth = total_new - total_old
    out = io.StringIO()
    if total_old == 0 or growth == 0:
        out.write("the bill did not move\n")
        return out.getvalue()
    out.write(
        f"the bill moved {growth / total_old:+.0%}, "
        f"{total_old} to {total_new}\n"
    )
    shares = []
    for space in set(before.cpu_ticks) | set(after.cpu_ticks):
        delta = after.cpu_ticks.get(space, 0) - before.cpu_ticks.get(space, 0)
        if delta:
            shares.append((delta, space))
    for delta, space in sorted(shares, key=lambda held: -abs(held[0])):
        out.write(f"  {space}: {delta / growth:+.0%} of the move\n")
    return out.getvalue()
