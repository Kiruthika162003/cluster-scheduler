"""Two generations, one request size: utilisation lies in both directions.

Eight identical tasks on two speed-1 and two speed-3 nodes. The blind
spread places two per node and the same work finishes in one tick on
new iron and three on old: a 3x finish gap that requested-cpu
utilisation, identical in every cell, cannot see. The speed-aware
scorer packs everything onto the new nodes and the gap collapses to
zero, at the price the trial refuses to hide: the old fleet idles at
zero tasks, so half the cluster's paper capacity turns out to be
either a tail or a stranding, and the profile only chooses which.
"""

from __future__ import annotations

from collections import Counter

from fleet.nodeprofile import WorkClock, profiled_node, speed_scorer
from fleet.objects import Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.scorers import spread
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _fleet(scorers: tuple) -> Store:
    store = Store()
    for number in range(2):
        store.add_node(profiled_node(f"old-{number}", cpu=1200, speed=1))
        store.add_node(profiled_node(f"new-{number}", cpu=1200, speed=3))
    scheduler = Scheduler(scorers=scorers)
    for number in range(8):
        store.add_task(
            Task(
                spec=TaskSpec(
                    name=f"t{number}", needs=Resources(cpu=300, memory=300)
                )
            )
        )
    scheduler.schedule_pending(store)
    return store


def run() -> Verdict:
    blind = _fleet((spread,))
    blind_clock = WorkClock(work_units=3)
    blind_clock.measure(blind)

    aware = _fleet((speed_scorer(),))
    aware_clock = WorkClock(work_units=3)
    aware_clock.measure(aware)

    old_iron_tasks = sum(
        1 for task in aware.active_tasks() if task.node.startswith("old")
    )
    numbers = {
        "blind_finish_spread": blind_clock.spread(),
        "blind_finishes": sorted(set(blind_clock.finish_ticks.values())),
        "aware_finish_spread": aware_clock.spread(),
        "aware_old_iron_tasks": old_iron_tasks,
        "placements_per_node_blind": dict(
            sorted(Counter(t.node for t in blind.active_tasks()).items())
        ),
    }
    holds = (
        blind_clock.spread() == 2
        and sorted(set(blind_clock.finish_ticks.values())) == [1, 3]
        and aware_clock.spread() == 0
        and old_iron_tasks == 0
    )
    return Verdict(
        trial="oldiron",
        sentence=(
            "the blind spread finishes identical work in 1 tick on new "
            "iron and 3 on old while utilisation reads identical; the "
            "speed-aware scorer collapses the gap to zero by stranding "
            "the old fleet at zero tasks, and the profile only chooses "
            "which lie utilisation tells"
        ),
        numbers=numbers,
        holds=holds,
    )
