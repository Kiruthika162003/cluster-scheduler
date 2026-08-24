"""The price of a verdict is fixed; the traffic share only sets the clock.

A broken canary at one percent of traffic takes twenty ticks to convict;
at twenty percent it takes one. The exposure meter shows why neither is
safer: conviction requires the same two hundred canary requests either
way, so the same number of users meet the broken build. The share does
not buy safety, it buys wall-clock, and the judge's refusal to rule
early is what keeps the evidence honest at any share.
"""

from __future__ import annotations

from fleet.roll.canary import MINIMUM_REQUESTS, Canary
from fleet.trials.verdict import Verdict


def _convict(share: float) -> tuple[int, int]:
    canary = Canary(traffic_share=share)
    ticks = 0
    while canary.state == "watching" and ticks < 1000:
        canary.tick(1000, stable_error_rate=0.01, canary_error_rate=0.30)
        ticks += 1
    return ticks, canary.canary.requests


def run() -> Verdict:
    slow_ticks, slow_exposed = _convict(0.01)
    fast_ticks, fast_exposed = _convict(0.20)
    healthy = Canary(traffic_share=0.01)
    ticks = 0
    while healthy.state == "watching" and ticks < 1000:
        healthy.tick(1000, stable_error_rate=0.01, canary_error_rate=0.01)
        ticks += 1

    numbers = {
        "ticks_at_1_percent": slow_ticks,
        "ticks_at_20_percent": fast_ticks,
        "exposed_at_1_percent": slow_exposed,
        "exposed_at_20_percent": fast_exposed,
        "healthy_promoted_after": ticks,
        "evidence_floor": MINIMUM_REQUESTS,
    }
    holds = (
        slow_ticks == 20
        and fast_ticks == 1
        and slow_exposed == fast_exposed == MINIMUM_REQUESTS
        and healthy.state == "promote"
    )
    return Verdict(
        trial="canaryevidence",
        sentence=(
            "convicting the broken build costs 200 canary requests at any "
            "traffic share; one percent pays them over twenty ticks and "
            "twenty percent in one, so the share sets the clock, not the "
            "blast radius"
        ),
        numbers=numbers,
        holds=holds,
    )
