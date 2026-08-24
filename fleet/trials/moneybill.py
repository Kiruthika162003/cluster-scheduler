"""Three scorers, one day, and a bill that depends on the alphabet once.

The frugal scorer chases the cheapest node per task and turns on seven
machines for a 2208 bill. The value scorer packs onto the best price
per unit of capacity and pays 1776 with three machines on. Binpack tied
the value scorer at 1776, then the trial renamed the small nodes so
they sort first and binpack's bill jumped to 2208: its win had been the
empty-cluster tie breaking toward big-0 because b sorts before s. A
policy whose bill moves 24 percent when the nodes are renamed is not a
cost policy; the money has to be in the scorer, not the sort order.
"""

from __future__ import annotations

from fleet.sched.cost import build_fleet, frugal_scorer, run_policy, value_scorer
from fleet.sched.scorers import binpack
from fleet.trials.verdict import Verdict


def run() -> Verdict:
    bills = {}
    for flip in (False, True):
        _, pricing = build_fleet(flip)
        for name, scorers in (
            ("frugal", (frugal_scorer(pricing),)),
            ("binpack", (binpack,)),
            ("value", (value_scorer(pricing),)),
        ):
            _, _, bill = run_policy(scorers, flip)
            bills[(name, flip)] = bill

    numbers = {
        "frugal": bills[("frugal", False)],
        "binpack_bigs_sort_first": bills[("binpack", False)],
        "binpack_smalls_sort_first": bills[("binpack", True)],
        "value_either_naming": bills[("value", False)],
    }
    holds = (
        bills[("frugal", False)] == bills[("frugal", True)] == 2208
        and bills[("binpack", False)] == 1776
        and bills[("binpack", True)] == 2208
        and bills[("value", False)] == bills[("value", True)] == 1776
    )
    return Verdict(
        trial="moneybill",
        sentence=(
            "frugal pays 2208 for seven machines, value pays 1776 for "
            "three under either naming, and binpack's 1776 became 2208 "
            "when the nodes were renamed: its win was the alphabet, not "
            "the arithmetic"
        ),
        numbers=numbers,
        holds=holds,
    )
