"""The overcommit gamble, repriced by its own measurement.

The first draft filled the node with requests, ten tenants of 100 on a
1000 node, and guessed the bet would hold through six simultaneous
bursters. Measured, the first burster already triggers an eviction:
requests that fill the node leave zero burst headroom, because headroom
is capacity minus requests, never anything about limits. With requests
at half, slack 500 against a burst excess of 200 each, the node holds
exactly floor(500 / 200) = 2 bursters and evicts on the third. The
gamble's odds are a formula, and the formula never mentions the limit.
"""

from __future__ import annotations

from fleet.objects import Node, Resources
from fleet.sched.qos import Ask, PressureNode
from fleet.trials.verdict import Verdict


def _loaded(request: int, limit: int) -> PressureNode:
    node = PressureNode(node=Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    for number in range(10):
        node.admit(
            Ask(
                f"b{number}",
                Resources(cpu=request, memory=request),
                Resources(cpu=limit, memory=limit),
            )
        )
    return node


def _evictions(request: int, limit: int, bursters: int) -> int:
    node = _loaded(request, limit)
    for number in range(bursters):
        node.burst(f"b{number}", Resources(cpu=limit, memory=limit))
    return len(node.relieve())


def _threshold(request: int, limit: int) -> int:
    for count in range(11):
        if _evictions(request, limit, count) > 0:
            return count
    return 11


def run() -> Verdict:
    full_threshold = _threshold(request=100, limit=250)
    slack_threshold = _threshold(request=50, limit=250)
    slack = 1000 - 10 * 50
    excess = 250 - 50
    predicted = slack // excess + 1
    stampede_full = _evictions(100, 250, 10)
    stampede_slack = _evictions(50, 250, 10)

    numbers = {
        "threshold_requests_full": full_threshold,
        "threshold_requests_half": slack_threshold,
        "formula_predicts": predicted,
        "stampede_evictions_full": stampede_full,
        "stampede_evictions_half": stampede_slack,
    }
    holds = (
        full_threshold == 1
        and slack_threshold == predicted == 3
        and stampede_full == stampede_slack == 6
    )
    return Verdict(
        trial="overcommit",
        sentence=(
            "requests that fill the node make the first burst an eviction; "
            "with requests at half the threshold is floor(slack over "
            "excess) plus one, measured 3 and predicted 3; a full stampede "
            "evicts six either way because relief frees whole bursters, "
            "and the limits never enter either formula"
        ),
        numbers=numbers,
        holds=holds,
    )
