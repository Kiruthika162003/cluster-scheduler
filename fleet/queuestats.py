"""Queue statistics: how long work waits, told as a distribution, not a mean.

The mean wait is the number managers ask for and the least useful one
in the building: a queue where most work places instantly and a tenth
starves shows a gentle mean and a furious tail. The stats page buckets
passes-waited into bands, names the longest waiter outright, and
reports the starving count from the queue's own definition, because
the tail is where the pain lives and the mean is where it hides.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from fleet.sched.queue import SchedulingQueue

BANDS = ((0, 1), (2, 5), (6, 20), (21, 10**9))
BAND_NAMES = ("instant", "short", "long", "stuck")


@dataclass(frozen=True)
class QueueStats:
    counts: tuple[int, ...]
    longest_name: str | None
    longest_waited: int
    waiting_total: int

    def render(self) -> str:
        out = io.StringIO()
        out.write(f"queue: {self.waiting_total} waiting\n")
        for name, count in zip(BAND_NAMES, self.counts, strict=True):
            out.write(f"  {name:<8} {count}\n")
        if self.longest_name is not None:
            out.write(
                f"  longest: {self.longest_name}, "
                f"{self.longest_waited} passes\n"
            )
        return out.getvalue()


def snapshot(queue: SchedulingQueue) -> QueueStats:
    counts = [0] * len(BANDS)
    longest_name = None
    longest_waited = -1
    for held in queue.waiting.values():
        for at, (low, high) in enumerate(BANDS):
            if low <= held.passes_waited <= high:
                counts[at] += 1
                break
        if held.passes_waited > longest_waited:
            longest_waited = held.passes_waited
            longest_name = held.name
    return QueueStats(
        counts=tuple(counts),
        longest_name=longest_name,
        longest_waited=max(longest_waited, 0),
        waiting_total=len(queue.waiting),
    )
