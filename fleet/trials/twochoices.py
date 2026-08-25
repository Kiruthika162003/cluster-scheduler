"""One slow endpoint, three policies: fairness in arrivals is not fairness.

Four fast endpoints serve every tick; one degraded straggler serves
every third. Round robin keeps feeding the straggler its fifth of the
traffic no matter what, and its queue grows to 140 over three hundred
ticks; pure random does the same by expectation, 110. Two random
choices peeks at the queue depth of two endpoints and takes the
shorter, and the straggler's queue never passes 3, because every
comparison it appears in sends the request elsewhere. The policy costs
one extra queue-depth read per request and no shared state, which is
why the power of two choices is the rare free lunch that measures like
one.
"""

from __future__ import annotations

from fleet.loadbalance import Balancer, Endpoint
from fleet.trials.verdict import Verdict


def _fleet() -> list[Endpoint]:
    endpoints = [
        Endpoint(name=f"fast-{number}", service_ticks=1) for number in range(4)
    ]
    endpoints.append(Endpoint(name="slow", service_ticks=3))
    return endpoints


def _run(policy: str) -> Balancer:
    balancer = Balancer(policy=policy, endpoints=_fleet())
    for now in range(1, 301):
        balancer.tick(now, arrivals=4)
    return balancer


def run() -> Verdict:
    robin = _run("round-robin")
    blind = _run("random")
    peeking = _run("two-choices")

    numbers = {
        "worst_depth_round_robin": robin.worst_depth,
        "worst_depth_random": blind.worst_depth,
        "worst_depth_two_choices": peeking.worst_depth,
    }
    holds = (
        robin.worst_depth == 140
        and blind.worst_depth == 110
        and peeking.worst_depth == 3
    )
    return Verdict(
        trial="twochoices",
        sentence=(
            "round robin grows the straggler's queue to 140 and random to "
            "110 because arrival fairness ignores service times; two "
            "random choices holds the worst queue at 3 for the price of "
            "one extra depth read per request"
        ),
        numbers=numbers,
        holds=holds,
    )
