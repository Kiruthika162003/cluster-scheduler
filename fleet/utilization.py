"""Utilisation honestly: allocated, requested, used, and the two gaps.

One number called utilisation hides two different wastes. The request
gap is capacity the scheduler gave away that nobody uses, owned by the
teams who over-asked; the allocation gap is capacity no one has claimed,
owned by the platform. The page reports both, per node and in total,
because the fix for each lives in a different meeting: right-sizing
requests in one, buying or shedding machines in the other.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from fleet.store import Store


@dataclass(frozen=True)
class NodeUse:
    name: str
    capacity: int
    requested: int
    used: int

    def request_gap(self) -> int:
        return max(0, self.requested - self.used)

    def allocation_gap(self) -> int:
        return max(0, self.capacity - self.requested)


def survey(store: Store, usage: dict[str, int]) -> list[NodeUse]:
    rows = []
    active = store.active_tasks()
    for name in sorted(store.nodes):
        node = store.nodes[name]
        tenants = [task for task in active if task.node == name]
        requested = sum(task.spec.needs.cpu for task in tenants)
        used = sum(usage.get(task.spec.name, 0) for task in tenants)
        rows.append(
            NodeUse(
                name=name,
                capacity=node.capacity.cpu,
                requested=requested,
                used=used,
            )
        )
    return rows


def totals(rows: list[NodeUse]) -> dict[str, int]:
    return {
        "capacity": sum(row.capacity for row in rows),
        "requested": sum(row.requested for row in rows),
        "used": sum(row.used for row in rows),
        "request_gap": sum(row.request_gap() for row in rows),
        "allocation_gap": sum(row.allocation_gap() for row in rows),
    }


def rendered(store: Store, usage: dict[str, int]) -> str:
    rows = survey(store, usage)
    whole = totals(rows)
    out = io.StringIO()
    out.write("node   capacity  requested  used  req_gap  alloc_gap\n")
    for row in rows:
        out.write(
            f"{row.name:<6} {row.capacity:<9} {row.requested:<10} "
            f"{row.used:<5} {row.request_gap():<8} {row.allocation_gap()}\n"
        )
    out.write(
        f"total  {whole['capacity']:<9} {whole['requested']:<10} "
        f"{whole['used']:<5} {whole['request_gap']:<8} {whole['allocation_gap']}\n"
    )
    if whole["capacity"]:
        out.write(
            f"teams waste {whole['request_gap'] / whole['capacity']:.0%} of the "
            f"cluster; the platform strands {whole['allocation_gap'] / whole['capacity']:.0%}\n"
        )
    return out.getvalue()
