"""The regression every error meter missed, caught by comparing answers.

The candidate build computes discounts with a rounding change: floor
instead of banker's rounding on the half-cents. It never throws, never
times out, and returns a well-formed price for all two thousand
mirrored requests, so its error rate is exactly production's and every
availability canary promotes it. The shadow diff compares the answers
themselves and finds the guess of a couple hundred disagreements was
generous: exactly half the requests, 1000 of 2000, price differently,
because 95 percent of a price lands on a half-cent for ten of every
twenty inputs. Wrong answers wearing 200s are invisible to every meter
except the one that checks the answer.
"""

from __future__ import annotations

from fleet.shadow import ShadowDiff
from fleet.trials.verdict import Verdict


def _production(cents: int) -> int:
    doubled = cents * 95
    return (doubled + 50) // 100


def _candidate(cents: int) -> int:
    return (cents * 95) // 100


def run() -> Verdict:
    diff = ShadowDiff()
    for cents in range(2000):
        diff.mirror(cents, _production, _candidate)

    told = diff.verdict(floor=0.999)
    numbers = {
        "compared": diff.compared,
        "disagreements": diff.compared - diff.agreed,
        "agreement": round(diff.agreement_rate(), 4),
        "verdict": told,
        "sampled": len(diff.samples),
    }
    holds = (
        diff.compared == 2000
        and diff.compared - diff.agreed == 1000
        and told.startswith("hold")
        and len(diff.samples) == 5
    )
    return Verdict(
        trial="shadowdiff",
        sentence=(
            "the rounding regression returns well-formed prices with "
            "production's exact error rate and every availability canary "
            "would promote it; the shadow diff finds half of all answers "
            "changed, 1000 of 2000, and holds the build"
        ),
        numbers=numbers,
        holds=holds,
    )
