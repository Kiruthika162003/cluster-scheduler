"""The eight-box rule is worth exactly one training job per wave.

Twelve two-slot jobs arrive ahead of one eight-slot training job,
into a pool of one eight-box and four four-boxes. Fewest-but-
sufficient placement packs the first eight small jobs onto the
four-boxes without touching the eight-box; the ninth has nowhere
else to go, lands on the eight-box, and the training job is
stranded. The rule delays the stranding to exactly the fleet's
small capacity and no further: headroom, not a guarantee, and
capacity planning that reads it as a guarantee will meet the
ninth job.
"""

from __future__ import annotations

from fleet.errors import NotFound
from fleet.sched.devices import DeviceNode, DevicePool
from fleet.trials.verdict import Verdict


def _pool() -> DevicePool:
    pool = DevicePool()
    pool.add_node(DeviceNode(name="big8", slots=8))
    for number in range(4):
        pool.add_node(DeviceNode(name=f"mid4-{number}", slots=4))
    return pool


def _jobs_until_stranded(pool: DevicePool) -> int:
    placed = 0
    for number in range(12):
        pool.place(f"small-{number}", count=2)
        placed += 1
        try:
            probe = DevicePool(
                nodes={
                    name: DeviceNode(
                        name=name,
                        slots=node.slots,
                        used=set(node.used),
                    )
                    for name, node in pool.nodes.items()
                }
            )
            probe.place("training-probe", count=8)
        except NotFound:
            return placed
    return placed


def run() -> Verdict:
    ruled = _jobs_until_stranded(_pool())
    numbers = {
        "small_jobs_before_stranding": ruled,
        "small_slots_in_the_fleet": 16,
    }
    holds = ruled == 9
    return Verdict(
        trial="eightbox",
        sentence=(
            "eight small jobs never touch the eight-box; the ninth "
            "strands the training job: headroom equal to the small "
            "capacity, not a guarantee"
        ),
        numbers=numbers,
        holds=holds,
    )
