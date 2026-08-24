"""Bin packing measured: the order is worth a third, the clever rule nothing.

On a friendly mix of five sizes every packer lands on 73 bins against an
arithmetic floor of 70, and neither sorting nor best-fit moves a single
bin. On the trap mix, a hundred 490s arriving ahead of a hundred 510s,
arrival order pairs the small halves and strands every large task alone:
150 bins where the floor is 100. Sorting largest-first hits the floor
exactly. Best-fit changes nothing in any cell, which is the measured
form of the classic result: what you pack first matters, how cleverly
you squeeze matters much less.
"""

from __future__ import annotations

from fleet.sched.offline import adversarial_mix, floor_bins, friendly_mix, pack
from fleet.trials.verdict import Verdict


def run() -> Verdict:
    friendly = friendly_mix()
    trap = adversarial_mix()
    cells = {}
    for name, sizes in (("friendly", friendly), ("trap", trap)):
        for rule in ("first", "best"):
            for decreasing in (False, True):
                packing = pack(sizes, rule, decreasing)
                cells[(name, rule, decreasing)] = len(packing.bins)

    numbers = {
        "floor_friendly": floor_bins(friendly),
        "friendly_all": sorted(
            {count for (name, _, _), count in cells.items() if name == "friendly"}
        ),
        "floor_trap": floor_bins(trap),
        "trap_arrival": cells[("trap", "first", False)],
        "trap_decreasing": cells[("trap", "first", True)],
        "best_ever_differs": any(
            cells[(name, "best", dec)] != cells[(name, "first", dec)]
            for name in ("friendly", "trap")
            for dec in (False, True)
        ),
    }
    holds = (
        numbers["floor_friendly"] == 70
        and numbers["friendly_all"] == [73]
        and numbers["floor_trap"] == 100
        and numbers["trap_arrival"] == 150
        and numbers["trap_decreasing"] == 100
        and not numbers["best_ever_differs"]
    )
    return Verdict(
        trial="packing",
        sentence=(
            "every packer ties at 73 on the friendly mix; on the trap the "
            "arrival order pays 150 bins against a floor of 100 that "
            "largest-first hits exactly, and best-fit never moves a bin "
            "in any cell"
        ),
        numbers=numbers,
        holds=holds,
    )
