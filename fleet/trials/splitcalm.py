"""The dwell is what separates a shard layout from a nervous tic.

Six shards: one burns 1200 continuously, one flaps to 1100 every
third tick and rests at 50 between, four idle at 100. Writing the
scenario taught the first lesson: with three shards the two hot
tenants lift the mean until neither crosses double it, so the
fleet needs its quiet majority for the threshold to mean anything.
With the dwell, the flapper's hot mark dies at one observation,
every cool tick resetting the clock, and it never splits in 40
ticks; the steady shard splits exactly once at its first eligible
tick, its load halves across the children, and the halves sit
under the new threshold, so the layout ends at seven shards and
stays there. One split, zero refusals, longest flapper streak one.
"""

from __future__ import annotations

from fleet.autosplit import Shard, Splitter
from fleet.trials.verdict import Verdict

STEADY_TOTAL = 1200


def _loads(splitter: Splitter, flapping_hot: bool) -> dict[int, int]:
    loads = {}
    for shard in splitter.shards:
        if shard.high <= 100:
            loads[shard.low] = STEADY_TOTAL * shard.width() // 100
        elif shard.low == 100:
            loads[shard.low] = 1100 if flapping_hot else 50
        else:
            loads[shard.low] = 100
    return loads


def run() -> Verdict:
    splitter = Splitter(
        shards=[Shard(low=0, high=100), Shard(low=100, high=200)]
        + [Shard(low=base, high=base + 100) for base in range(200, 600, 100)],
        move_budget=10_000,
    )
    actions = []
    flapper_streak = longest_streak = 0
    for now in range(40):
        acted = splitter.observe(_loads(splitter, now % 3 == 0), now)
        actions.extend(acted)
        flapper = next(s for s in splitter.shards if s.low == 100)
        if flapper.hot_since is not None:
            flapper_streak += 1
            longest_streak = max(longest_streak, flapper_streak)
        else:
            flapper_streak = 0
    splits = [line for line in actions if line.startswith("split")]
    numbers = {
        "splits": len(splits),
        "refusals": len(splitter.refused),
        "final_shards": len(splitter.shards),
        "flapper_longest_hot_streak": longest_streak,
    }
    holds = (
        numbers["splits"] == 1
        and numbers["refusals"] == 0
        and numbers["final_shards"] == 7
        and longest_streak == 1
        and splits[0].startswith("split [0,100)")
    )
    return Verdict(
        trial="splitcalm",
        sentence=(
            "the steady shard splits once and its halves stay whole; the "
            "flapper's hot mark dies at one observation, forty ticks, "
            "zero splits"
        ),
        numbers=numbers,
        holds=holds,
    )
