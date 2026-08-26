"""Backfill rents out the dead hours; the eviction bill turns out to be zero.

A 600m hold opens at tick 50. Without backfill the held cpu idles
for 50 ticks: 30000 cpu-ticks of paid silence. The guess was 6
finishes and 3 edge evictions. The measurement says 9 finish and
the eviction column is zero, because the admission gate already
refuses any job that cannot finish before the window: for truthful
declarations, eviction is structurally impossible, and the sweep is
insurance against liars and overruns only. The 10 percent left idle
is quantization, a 5-tick tail shorter than one 15-tick job. 27000
of 30000 cpu-ticks earn rent and the hold opens on time with its
full 600m, the only number the launch team ever checks.
"""

from __future__ import annotations

from fleet.backfill import Backfiller
from fleet.holds import Hold, HoldLedger
from fleet.objects import Node, Resources
from fleet.trials.verdict import Verdict

WINDOW_OPENS = 50
JOB_CPU = 200
JOB_TICKS = 15


def run() -> Verdict:
    ledger = HoldLedger()
    node = Node(name="n0", capacity=Resources(cpu=1000, memory=1000))
    ledger.book(
        Hold(
            name="launch",
            node="n0",
            amount=Resources(cpu=600, memory=600),
            starts=WINDOW_OPENS,
            ends=WINDOW_OPENS + 30,
        ),
        node,
    )
    filler = Backfiller(ledger=ledger)
    active: dict[str, int] = {}
    job_number = 0
    for now in range(WINDOW_OPENS + 1):
        for task in [name for name, ends in active.items() if ends <= now]:
            filler.finish(task, now)
            del active[task]
        for _ in range(3):
            name = f"job-{job_number}"
            loan = filler.borrow(
                name, cpu=JOB_CPU, needs_ticks=JOB_TICKS, node="n0", now=now
            )
            if loan is None:
                break
            active[name] = now + JOB_TICKS
            job_number += 1
        swept = filler.sweep(now)
        for task in swept:
            active.pop(task, None)
    idle_ticks = WINDOW_OPENS * 600
    numbers = {
        "possible_cpu_ticks": idle_ticks,
        "lent_cpu_ticks": filler.lent_ticks,
        "finished": filler.finished,
        "evicted": filler.evictions,
        "utilisation_pct": round(100 * filler.lent_ticks / idle_ticks),
    }
    holds = (
        numbers["lent_cpu_ticks"] == 27000
        and numbers["finished"] == 9
        and numbers["evicted"] == 0
        and numbers["utilisation_pct"] == 90
    )
    return Verdict(
        trial="backfillrent",
        sentence=(
            "the admission gate makes eviction impossible for truthful "
            "jobs: 9 finish, 0 evicted, 90 percent of the idle rented"
        ),
        numbers=numbers,
        holds=holds,
    )
