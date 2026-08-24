"""The preference dial is a step: zero does nothing and epsilon does it all.

Ten 200m tasks, four big hdd nodes and four small ssd nodes that
physically hold two tasks each. At weight zero the packer uses two hdd
machines and grants no wishes. At the smallest tested weight, 0.05, the
outcome jumps straight to the physical maximum: satisfaction 0.8, five
machines on, and every larger weight up to 5.0 reproduces it exactly.
The wish only needs to win the empty-cluster tie once; after that the
fullness fraction favours the small ssd nodes on its own, because half
of a 400m node reads as fuller than a fifth of a 1000m one. The cap at
0.8 is capacity, not conviction: the ssd fleet holds eight tasks, so
two must live unhappy wherever the weight is set.
"""

from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.soft import Wish, blended, nodes_used, satisfaction
from fleet.store import Store
from fleet.trials.verdict import Verdict

WISHES = (Wish(label="disk", value="ssd", weight=1.0),)


def _placed(weight: float) -> Store:
    store = Store()
    for number in range(4):
        store.add_node(
            Node(
                name=f"hdd-{number}",
                capacity=Resources(cpu=1000, memory=1000),
                labels={"disk": "hdd"},
            )
        )
        store.add_node(
            Node(
                name=f"ssd-{number}",
                capacity=Resources(cpu=400, memory=400),
                labels={"disk": "ssd"},
            )
        )
    scheduler = Scheduler(scorers=(blended(WISHES, weight),))
    for number in range(10):
        store.add_task(
            Task(
                spec=TaskSpec(
                    name=f"t{number}", needs=Resources(cpu=200, memory=200)
                )
            )
        )
    scheduler.schedule_pending(store)
    return store


def run() -> Verdict:
    outcomes = {}
    for weight in (0.0, 0.05, 0.2, 1.0, 5.0):
        store = _placed(weight)
        outcomes[weight] = (
            round(satisfaction(store, WISHES), 2),
            nodes_used(store),
        )

    nonzero = {outcome for weight, outcome in outcomes.items() if weight > 0}
    numbers = {
        "at_zero": outcomes[0.0],
        "at_epsilon": outcomes[0.05],
        "nonzero_outcomes_identical": len(nonzero) == 1,
        "ssd_slots": 8,
    }
    holds = (
        outcomes[0.0] == (0.0, 2)
        and outcomes[0.05] == (0.8, 5)
        and len(nonzero) == 1
    )
    return Verdict(
        trial="softstep",
        sentence=(
            "weight zero grants nothing on two machines; weight 0.05 "
            "jumps straight to the capacity cap of 0.8 on five machines "
            "and every larger weight reproduces it exactly, because the "
            "wish only needs to win the empty-cluster tie once"
        ),
        numbers=numbers,
        holds=holds,
    )
