"""A whole zone dies at once: the spread you paid for is the fleet you keep.

Six nodes in three zones, nine replicas placed twice: once by binpack,
which stacks them into zone a, and once under the topology skew cap,
which lands three per zone. Zone a then fails as one event, the way
zones do. The packed fleet keeps zero of nine serving; the spread
fleet keeps six. Same capacity, same workload, same failure, and the
whole difference was decided at placement time by a constraint that
looked like bureaucracy until the power strip went."""

from __future__ import annotations

from collections import Counter

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.filters import EVERY_FILTER
from fleet.sched.scorers import binpack
from fleet.sched.topology import SpreadRule, spread_filter, zone_map
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _zoned_store() -> Store:
    store = Store()
    for number in range(6):
        zone = ("a", "b", "c")[number // 2]
        store.add_node(
            Node(
                name=f"n{number}",
                capacity=Resources(cpu=2000, memory=2000),
                labels={"zone": zone},
            )
        )
    return store


def _place(spread: bool) -> Store:
    store = _zoned_store()
    filters = EVERY_FILTER
    if spread:
        rule = SpreadRule(label_key="app", label_value="web", max_skew=1)
        zones = zone_map(list(store.nodes.values()))
        filters = (*EVERY_FILTER, spread_filter(rule, zones))
    scheduler = Scheduler(scorers=(binpack,), filters=filters)
    for number in range(9):
        store.add_task(
            Task(
                spec=TaskSpec(
                    name=f"w{number}",
                    needs=Resources(cpu=400, memory=400),
                    labels=(("app", "web"),),
                )
            )
        )
    scheduler.schedule_pending(store)
    return store


def _fail_zone(store: Store, zone: str) -> int:
    for node in store.nodes.values():
        if node.labels.get("zone") == zone:
            node.ready = False
    return sum(
        1
        for task in store.active_tasks()
        if store.nodes[task.node].ready
    )


def run() -> Verdict:
    packed = _place(spread=False)
    packed_zones = Counter(
        packed.nodes[task.node].labels["zone"] for task in packed.active_tasks()
    )
    packed_surviving = _fail_zone(packed, "a")

    spread_out = _place(spread=True)
    spread_zones = Counter(
        spread_out.nodes[task.node].labels["zone"]
        for task in spread_out.active_tasks()
    )
    spread_surviving = _fail_zone(spread_out, "a")

    numbers = {
        "packed_by_zone": dict(sorted(packed_zones.items())),
        "spread_by_zone": dict(sorted(spread_zones.items())),
        "packed_surviving_zone_a_loss": packed_surviving,
        "spread_surviving_zone_a_loss": spread_surviving,
    }
    holds = (
        packed_zones == Counter({"a": 9})
        and spread_zones == Counter({"a": 3, "b": 3, "c": 3})
        and packed_surviving == 0
        and spread_surviving == 6
    )
    return Verdict(
        trial="zoneloss",
        sentence=(
            "binpack stacks all nine replicas into zone a and the zone "
            "failure keeps zero serving; the skew cap of one lands three "
            "per zone and keeps six, the whole difference decided at "
            "placement time"
        ),
        numbers=numbers,
        holds=holds,
    )
