"""Spreading strands capacity in slivers; packing keeps a door open.

Forty small tasks land on ten nodes under each placement policy, then a
task the size of a whole node asks to come in. Total free capacity is
identical either way. Whether the big task fits depends entirely on the
shape of the free space, which is the entire argument between the two
scorers and the reason neither is simply right.
"""

from __future__ import annotations

from fleet.errors import Unschedulable
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.scorers import binpack, spread
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _cluster() -> Store:
    store = Store()
    for number in range(10):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    return store


def _fill(store: Store, scorer) -> Scheduler:
    scheduler = Scheduler(scorers=(scorer,))
    for number in range(40):
        store.add_task(
            Task(
                spec=TaskSpec(
                    name=f"small-{number:02d}", needs=Resources(cpu=150, memory=150)
                )
            )
        )
    scheduler.schedule_pending(store)
    return scheduler


def _big_fits(store: Store) -> bool:
    big = Task(spec=TaskSpec(name="big", needs=Resources(cpu=1000, memory=1000)))
    store.add_task(big)
    try:
        Scheduler().schedule(store, big)
    except Unschedulable:
        return False
    return True


def run() -> Verdict:
    packed = _cluster()
    _fill(packed, binpack)
    spread_out = _cluster()
    _fill(spread_out, spread)

    packed_nodes_used = len({t.node for t in packed.active_tasks()})
    spread_nodes_used = len({t.node for t in spread_out.active_tasks()})
    free_total = 10 * 1000 - 40 * 150
    packed_admits = _big_fits(packed)
    spread_admits = _big_fits(spread_out)

    numbers = {
        "free_cpu_either_way": free_total,
        "nodes_used_packed": packed_nodes_used,
        "nodes_used_spread": spread_nodes_used,
        "big_admitted_packed": packed_admits,
        "big_admitted_spread": spread_admits,
    }
    holds = (
        free_total == 4000
        and packed_nodes_used == 7
        and spread_nodes_used == 10
        and packed_admits
        and not spread_admits
    )
    return Verdict(
        trial="fragmentation",
        sentence=(
            "with 4000m free either way, packing onto 7 nodes admits the "
            "node-sized task and spreading over 10 strands the same "
            "capacity in ten 600m slivers"
        ),
        numbers=numbers,
        holds=holds,
    )
