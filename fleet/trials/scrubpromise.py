"""The scrub cycle is a promise, and growth quietly rewrites it.

A thousand blocks scrubbed at 50 per tick promise detection within
20 ticks, and the worst-placed corruption, planted just behind the
cursor, surfaces at exactly 20: the guess said one tick inside the
promise, the measurement says the promise is tight to the tick.
Then the fleet doubles with the rate untouched and the same
worst-case find lands at exactly 40. Nothing failed, no alert
fired, and the detection guarantee
halved, which is why the planner exists: naming the promise first
and deriving the rate, 100 per tick to hold 20 ticks at double
size, turns silent erosion into a line item the capacity review
can see.
"""

from __future__ import annotations

from fleet.scrubber import Scrubber, rate_for_promise
from fleet.trials.verdict import Verdict


def _worst_case_find(block_count: int, rate: int) -> int:
    scrubber = Scrubber(
        blocks=[f"b{number}" for number in range(block_count)], rate=rate
    )
    scrubber.tick(now=0)
    scrubber.mark_corrupt("b0")
    for tick in range(1, scrubber.cycle_ticks() + 2):
        if scrubber.tick(now=tick):
            return tick
    return -1


def run() -> Verdict:
    numbers = {
        "find_at_1000_blocks": _worst_case_find(1000, rate=50),
        "find_at_2000_blocks": _worst_case_find(2000, rate=50),
        "rate_to_restore_promise": rate_for_promise(
            block_count=2000, within_ticks=20
        ),
    }
    holds = (
        numbers["find_at_1000_blocks"] == 20
        and numbers["find_at_2000_blocks"] == 40
        and numbers["rate_to_restore_promise"] == 100
    )
    return Verdict(
        trial="scrubpromise",
        sentence=(
            "the promise is tight to the tick: worst-case detection moves "
            "from exactly 20 to exactly 40; holding it costs rate "
            "100, a line item the review can see"
        ),
        numbers=numbers,
        holds=holds,
    )
