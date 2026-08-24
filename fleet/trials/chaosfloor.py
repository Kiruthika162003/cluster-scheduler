"""Twenty five storms, two meters: the dashboard never blinked, the truth did.

Every seeded storm reports a dashboard floor of 8 of 8, because tasks on
a dead node keep the phase Running until the eviction grace expires and
the replacement lands the same tick the ghosts vanish. The truthful
meter, running tasks on nodes that are actually ready, dips to 4 in the
worst storm, two overlapping node deaths. The gap between the meters is
not measurement noise; it is the exact population of ghosts the ghosts
trial demonstrated one node at a time, here surviving every one of
twenty five adversarial schedules.
"""

from __future__ import annotations

from collections import Counter

from fleet.chaos import Chaos
from fleet.trials.verdict import Verdict


def run() -> Verdict:
    chaos = Chaos()
    truthful_floor = chaos.campaign(seeds=25)
    dashboards = Counter(report.worst for report in chaos.reports)
    truthfuls = Counter(report.truthful for report in chaos.reports)
    worst = chaos.worst_storm()

    again = Chaos()
    again.campaign(seeds=25)
    reproducible = [
        (report.seed, report.truthful) for report in chaos.reports
    ] == [(report.seed, report.truthful) for report in again.reports]

    numbers = {
        "storms": 25,
        "dashboard_floors": dict(dashboards),
        "truthful_floors": dict(sorted(truthfuls.items())),
        "worst_seed": worst.seed,
        "worst_truthful": worst.truthful,
        "reproducible": reproducible,
    }
    holds = (
        dashboards == Counter({8: 25})
        and truthful_floor == 4
        and worst.seed == 13
        and reproducible
    )
    return Verdict(
        trial="chaosfloor",
        sentence=(
            "the dashboard floor is 8 in all 25 storms while the truthful "
            "floor reaches 4 under two overlapping node deaths; the gap is "
            "the ghost population, and every storm replays exactly from "
            "its seed"
        ),
        numbers=numbers,
        holds=holds,
    )
