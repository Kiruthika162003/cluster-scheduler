"""The lame duck's bill: every request the hard kill would have broken.

Twenty requests are in flight when the deploy wants the process
gone. The hard kill converts all twenty into user-visible errors
at that instant; the choreographed shutdown refuses the six that
arrive during the duck, finishes all twenty it holds inside the
drain deadline, and cuts nothing. The refused six are not errors,
they are retries the balancer lands elsewhere, which is the whole
moral difference between refusing work you have not taken and
breaking work you have. The epitaph reads graceful, and its cut
column, zero against the hard kill's twenty, is the number the
deploy pipeline should print beside every restart.
"""

from __future__ import annotations

from fleet.gracefulshutdown import Shutdown
from fleet.trials.verdict import Verdict

IN_FLIGHT = 20
LATE_ARRIVALS = 6


def run() -> Verdict:
    shutdown = Shutdown(drain_deadline=30)
    for number in range(IN_FLIGHT):
        shutdown.accept(f"held-{number}", now=0, takes=8 + number % 5)
    hard_kill_errors = len(shutdown.in_flight)
    shutdown.begin(now=1)
    for number in range(LATE_ARRIVALS):
        shutdown.accept(f"late-{number}", now=2 + number, takes=3)
    outcome = "draining"
    tick = 2
    while outcome not in ("closed clean",) and not outcome.startswith(
        "closed hard"
    ):
        outcome = shutdown.tick(now=tick)
        tick += 1
    numbers = {
        "hard_kill_would_break": hard_kill_errors,
        "refused_during_duck": shutdown.refused,
        "finished_in_drain": shutdown.finished,
        "cut_at_deadline": len(shutdown.cut),
    }
    holds = (
        numbers["hard_kill_would_break"] == 20
        and numbers["refused_during_duck"] == 6
        and numbers["finished_in_drain"] == 20
        and numbers["cut_at_deadline"] == 0
        and outcome == "closed clean"
    )
    return Verdict(
        trial="duckbill",
        sentence=(
            "the hard kill breaks 20; the duck refuses 6 it never took, "
            "finishes all 20 it held, and cuts none"
        ),
        numbers=numbers,
        holds=holds,
    )
