"""The hedge delay is a dial between two currencies, and the curve says where.

The same workload runs at four hedge delays: 95 calls at latency 10
and five stragglers at 300, backups always fast. Delay zero buys
p99 of 12 for 100 percent extra load, a traffic doubling; delay 50
buys p99 of 62 for 5 percent; delay 150 still catches the
stragglers at p99 162 for the same 5 percent, because the payers
are exactly the five calls slower than any sane delay; and delay
301 hedges nothing, p99 300 for zero. The lesson the curve makes
unavoidable: between 50 and 150 the extra load does not move at
all, only the latency does, so the dial's useful range is narrower
than it looks and the price of panic (delay zero) is twenty times
the price of patience.
"""

from __future__ import annotations

from fleet.hedging import Hedger
from fleet.trials.verdict import Verdict

DELAYS = (0, 50, 150, 301)


def _run(delay: int) -> tuple[int, float]:
    hedger = Hedger(hedge_delay=delay)
    for _ in range(95):
        hedger.call(primary_latency=10, backup_latency=12)
    for _ in range(5):
        hedger.call(primary_latency=300, backup_latency=12)
    p99 = hedger.percentile(hedger.delivered_latencies(), 0.99)
    return p99, hedger.extra_load()


def run() -> Verdict:
    curve = {delay: _run(delay) for delay in DELAYS}
    numbers = {
        f"p99_at_{delay}": curve[delay][0] for delay in DELAYS
    }
    numbers.update(
        {f"load_at_{delay}": curve[delay][1] for delay in DELAYS}
    )
    holds = (
        curve[0] == (12, 1.0)
        and curve[50] == (62, 0.05)
        and curve[150] == (162, 0.05)
        and curve[301] == (300, 0.0)
    )
    return Verdict(
        trial="hedgeprice",
        sentence=(
            "between delay 50 and 150 the load never moves and only "
            "latency does; panic at delay zero costs twenty times "
            "patience"
        ),
        numbers=numbers,
        holds=holds,
    )
