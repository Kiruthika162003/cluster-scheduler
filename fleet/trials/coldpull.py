"""Image locality: 32 pull-ticks saved, and the fleet folded onto two nodes.

Six replicas of an image warmed on two of six nodes. The blind spread
starts four of them cold, 32 pull-ticks of start latency, and warms
four more caches as a side effect. The locality scorer lands all six
on the two warm nodes: zero pulls, zero delayed starts, and the whole
service now lives on a third of the fleet, which is the concentration
the savings bought. Quote the two numbers together or not at all: the
pull you skip is the fastest pull there is, and the blast radius you
grow is the widest one.
"""

from __future__ import annotations

from collections import Counter

from fleet.imagecache import ImageCaches, start_all
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.scorers import spread
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _fleet(scorers: tuple, caches: ImageCaches) -> Store:
    store = Store()
    for number in range(6):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    caches.warm("n0", "app:v1")
    caches.warm("n1", "app:v1")
    scheduler = Scheduler(scorers=scorers)
    for number in range(6):
        store.add_task(
            Task(
                spec=TaskSpec(
                    name=f"t{number}",
                    needs=Resources(cpu=300, memory=300),
                    labels=(("image", "app:v1"),),
                )
            )
        )
    scheduler.schedule_pending(store)
    return store


def run() -> Verdict:
    blind_caches = ImageCaches()
    blind = _fleet((spread,), blind_caches)
    blind_delays = start_all(blind, blind_caches)

    local_caches = ImageCaches()
    local = _fleet(
        (spread, local_caches.locality_scorer(weight=2.0)), local_caches
    )
    local_delays = start_all(local, local_caches)

    numbers = {
        "pull_ticks_blind": blind_caches.pull_ticks_spent,
        "cold_starts_blind": sum(1 for d in blind_delays.values() if d),
        "pull_ticks_local": local_caches.pull_ticks_spent,
        "cold_starts_local": sum(1 for d in local_delays.values() if d),
        "nodes_hosting_blind": len(Counter(t.node for t in blind.active_tasks())),
        "nodes_hosting_local": len(Counter(t.node for t in local.active_tasks())),
    }
    holds = (
        blind_caches.pull_ticks_spent == 32
        and numbers["cold_starts_blind"] == 4
        and local_caches.pull_ticks_spent == 0
        and numbers["cold_starts_local"] == 0
        and numbers["nodes_hosting_local"] == 2
    )
    return Verdict(
        trial="coldpull",
        sentence=(
            "the blind spread starts four replicas cold for 32 pull-ticks "
            "across six nodes; the locality scorer starts all six warm on "
            "two nodes, and the zero delay and the third-of-the-fleet "
            "blast radius are the same decision"
        ),
        numbers=numbers,
        holds=holds,
    )
