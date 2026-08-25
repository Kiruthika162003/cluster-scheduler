"""Chatty services priced in hops: attraction buys locality the spread sells.

A frontend makes twenty calls a tick to its cache. A call on the same
node costs one hop; across nodes, ten. Under the spread scorer the
four frontend-cache pairs land on eight different nodes and the fleet
pays 800 hops a tick. The first attraction scorer pulled every
frontend toward the same cache crowd and co-located zero pairs, the
measured difference between liking caches and knowing your own: the
partner-aware scorer reads the moving task's pair label and co-locates
all four for 80 hops. Spread is for surviving a node loss, attraction
is for the latency bill, and the policy chooses which bill arrives.
"""

from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.scorers import attracted_to_partner, spread
from fleet.store import Store
from fleet.trials.verdict import Verdict

PAIRS = 4
CALLS = 20
LOCAL_HOP = 1
REMOTE_HOP = 10


def _cluster() -> Store:
    store = Store()
    for number in range(8):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    return store


def _place(scorers: tuple) -> Store:
    store = _cluster()
    scheduler = Scheduler(scorers=scorers)
    for number in range(PAIRS):
        cache = Task(
            spec=TaskSpec(
                name=f"cache-{number}",
                needs=Resources(cpu=300, memory=300),
                labels=(("role", "cache"), ("pair", str(number))),
            )
        )
        store.add_task(cache)
    scheduler.schedule_pending(store)
    for number in range(PAIRS):
        front = Task(
            spec=TaskSpec(
                name=f"front-{number}",
                needs=Resources(cpu=300, memory=300),
                labels=(("role", "front"), ("pair", str(number))),
            )
        )
        store.add_task(front)
    scheduler.schedule_pending(store)
    return store


def _hops_per_tick(store: Store) -> int:
    total = 0
    for number in range(PAIRS):
        front = store.get_task(f"front-{number}")
        cache = store.get_task(f"cache-{number}")
        cost = LOCAL_HOP if front.node == cache.node else REMOTE_HOP
        total += CALLS * cost
    return total


def run() -> Verdict:
    spread_out = _place((spread,))
    drawn = _place((spread, attracted_to_partner("pair", weight=5.0)))

    spread_bill = _hops_per_tick(spread_out)
    drawn_bill = _hops_per_tick(drawn)
    co_located = sum(
        1
        for number in range(PAIRS)
        if drawn.get_task(f"front-{number}").node
        == drawn.get_task(f"cache-{number}").node
    )

    numbers = {
        "hops_spread": spread_bill,
        "hops_attracted": drawn_bill,
        "pairs_co_located": co_located,
        "nodes_used_spread": len({t.node for t in spread_out.active_tasks()}),
        "nodes_used_attracted": len({t.node for t in drawn.active_tasks()}),
    }
    holds = (
        spread_bill == 800
        and drawn_bill == 80
        and co_located == PAIRS
    )
    return Verdict(
        trial="chattyhops",
        sentence=(
            "spread lands the four chatty pairs on eight nodes for 800 "
            "hops a tick; attraction co-locates every pair for 80: spread "
            "is for surviving a node loss, attraction is for the latency "
            "bill, and the policy chooses which bill arrives"
        ),
        numbers=numbers,
        holds=holds,
    )
