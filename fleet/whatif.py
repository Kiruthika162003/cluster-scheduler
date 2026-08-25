"""What-if planning: rehearse the fleet change, keep the receipts, touch nothing.

Every question is a copy: what if we add four nodes, lose zone b, or
double the web deploy. The planner runs the change against a snapshot
restore and reports headroom, N+1, and stranding deltas side by side
with today, guaranteed not to touch the live store because it never
holds a reference to it. The receipts read as before, after, delta,
because a what-if that only shows the after is an ad.
"""

from __future__ import annotations

import io

from fleet.capacityplan import survives_n_plus_one
from fleet.objects import Node, Resources, free
from fleet.snapshot import dump, restore
from fleet.store import Store


def _headroom(store: Store) -> int:
    active = store.active_tasks()
    return sum(
        free(node, active).cpu
        for node in store.nodes.values()
        if node.ready and node.schedulable
    )


def _measure(store: Store) -> dict:
    survives, why = survives_n_plus_one(store)
    return {
        "nodes": len(store.nodes),
        "headroom_cpu": _headroom(store),
        "n_plus_one": survives,
        "n_plus_one_why": why,
    }


def what_if_add_nodes(store: Store, count: int, cpu: int) -> dict:
    twin = restore(dump(store))
    for number in range(count):
        twin.nodes[f"whatif-{number}"] = Node(
            name=f"whatif-{number}",
            capacity=Resources(cpu=cpu, memory=cpu),
        )
    return {"before": _measure(store), "after": _measure(twin)}


def what_if_lose_zone(store: Store, zone: str) -> dict:
    twin = restore(dump(store))
    for node in twin.nodes.values():
        if node.labels.get("zone") == zone:
            node.ready = False
    return {"before": _measure(store), "after": _measure(twin)}


def rendered(question: str, result: dict) -> str:
    out = io.StringIO()
    out.write(f"what if {question}\n")
    before, after = result["before"], result["after"]
    for key in ("nodes", "headroom_cpu"):
        delta = after[key] - before[key]
        out.write(f"  {key}: {before[key]} -> {after[key]} ({delta:+d})\n")
    out.write(
        f"  n+1: {'ok' if before['n_plus_one'] else 'AT RISK'} -> "
        f"{'ok' if after['n_plus_one'] else 'AT RISK'}\n"
    )
    out.write(f"  because: {after['n_plus_one_why']}\n")
    return out.getvalue()
