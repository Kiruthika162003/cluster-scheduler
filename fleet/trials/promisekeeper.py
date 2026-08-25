"""Three queue disciplines, five promises, and the one that keeps them all.

Five batch jobs with deadlines run on one machine. Shortest-job-first
minimises waiting and burns the long job with the near deadline by 60.
FIFO meets every deadline in the first world, then the same jobs
arrive in a different order and FIFO is 30 late: its success was the
arrival order flattering it. Earliest-deadline-first meets every
promise in both worlds with the same worst slack of minus ten, because
it is the only discipline of the three that ever read the deadlines.
"""

from __future__ import annotations

from fleet.sched.deadline import BatchJob, jobs_late, max_lateness
from fleet.trials.verdict import Verdict

FRIENDLY = [
    BatchJob("etl-long", duration=50, deadline=60),
    BatchJob("report-quick", duration=5, deadline=100),
    BatchJob("index-mid", duration=20, deadline=90),
    BatchJob("export-quick", duration=5, deadline=110),
    BatchJob("train-long", duration=40, deadline=200),
]

SCRAMBLED = [FRIENDLY[4], FRIENDLY[0], FRIENDLY[2], FRIENDLY[1], FRIENDLY[3]]


def run() -> Verdict:
    numbers = {
        "sjf_max_lateness": max_lateness(FRIENDLY, "sjf"),
        "sjf_late_jobs": jobs_late(FRIENDLY, "sjf"),
        "fifo_friendly": max_lateness(FRIENDLY, "fifo"),
        "fifo_scrambled": max_lateness(SCRAMBLED, "fifo"),
        "edf_friendly": max_lateness(FRIENDLY, "edf"),
        "edf_scrambled": max_lateness(SCRAMBLED, "edf"),
    }
    holds = (
        numbers["sjf_max_lateness"] == 60
        and numbers["sjf_late_jobs"] == 1
        and numbers["fifo_friendly"] == -10
        and numbers["fifo_scrambled"] == 30
        and numbers["edf_friendly"] == numbers["edf_scrambled"] == -10
    )
    return Verdict(
        trial="promisekeeper",
        sentence=(
            "shortest-first burns the long promise by 60, FIFO meets "
            "every deadline until the arrival order stops flattering it "
            "and then misses by 30, and earliest-deadline-first keeps "
            "every promise in both worlds because it alone read them"
        ),
        numbers=numbers,
        holds=holds,
    )
