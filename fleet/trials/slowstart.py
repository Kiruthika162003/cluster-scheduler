"""Slow start fixes the balancer that needed it and taxes the one that did not.

A cold endpoint joins mid-run serving six times slower for its first
thirty ticks. Depth-blind round robin floods it to a worst queue of 18;
the slow-start ramp trickles it in and the worst queue is 7. Under two
random choices the same newcomer never passes 2 without any ramp,
because the depth comparison is already a throttle, and adding the
ramp anyway pushes its worst queue to 4 by starving the signal the
policy runs on. Slow start is a prosthetic for depth-blindness, and
strapping it onto a sighted balancer makes the balancer worse.
"""

from __future__ import annotations

from fleet.loadbalance import Balancer, Endpoint
from fleet.trials.verdict import Verdict


def _cold_worst(policy: str, slow_start: int) -> int:
    endpoints = [
        Endpoint(name=f"warm-{number}", service_ticks=1) for number in range(3)
    ]
    balancer = Balancer(
        policy=policy, endpoints=endpoints, slow_start=slow_start
    )
    cold = None
    worst = 0
    for now in range(1, 121):
        if now == 50:
            cold = Endpoint(
                name="cold",
                service_ticks=1,
                joined_at=50,
                cold_period=6,
                cold_for=30,
            )
            balancer.endpoints.append(cold)
        balancer.tick(now, arrivals=3)
        if cold is not None:
            worst = max(worst, cold.queue)
    return worst


def run() -> Verdict:
    numbers = {
        "rr_bare": _cold_worst("round-robin", 0),
        "rr_ramped": _cold_worst("round-robin", 30),
        "two_choices_bare": _cold_worst("two-choices", 0),
        "two_choices_ramped": _cold_worst("two-choices", 30),
    }
    holds = (
        numbers["rr_bare"] == 18
        and numbers["rr_ramped"] == 7
        and numbers["two_choices_bare"] == 2
        and numbers["two_choices_ramped"] == 4
    )
    return Verdict(
        trial="slowstart",
        sentence=(
            "round robin floods the cold newcomer to 18 and the ramp "
            "holds it to 7; two random choices holds it to 2 with no "
            "ramp at all and the ramp pushes it to 4: slow start is a "
            "prosthetic for depth-blindness, harmful on a sighted "
            "balancer"
        ),
        numbers=numbers,
        holds=holds,
    )
