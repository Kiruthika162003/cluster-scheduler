"""Chargeback: the cluster bill split by namespace, with the idle rump shown.

The bill is per node-hour; the split is by requested share of each
occupied node; and whatever no namespace requested is the idle rump,
charged to the platform line rather than smeared across the tenants,
because smearing idle capacity over teams teaches them that efficiency
is someone else's rounding error. Requested, not used, is the billing
basis: you pay for what you reserved, which is what the scheduler
could not give anyone else.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from fleet.store import Store


@dataclass(frozen=True)
class BillLine:
    namespace: str
    node_share: float
    charge: float


def split_bill(
    store: Store, hourly: dict[str, int], hours: int = 24
) -> tuple[list[BillLine], float]:
    """Per namespace lines plus the platform's idle charge."""
    by_space: dict[str, float] = {}
    idle_charge = 0.0
    active = store.active_tasks()
    for node_name, node in store.nodes.items():
        tenants = [task for task in active if task.node == node_name]
        if not tenants:
            continue
        price = hourly[node_name] * hours
        requested = sum(task.spec.needs.cpu for task in tenants)
        used_fraction = min(1.0, requested / node.capacity.cpu)
        for task in tenants:
            share = task.spec.needs.cpu / node.capacity.cpu
            by_space[task.spec.namespace] = (
                by_space.get(task.spec.namespace, 0.0) + share * price
            )
        idle_charge += (1.0 - used_fraction) * price
    lines = [
        BillLine(
            namespace=space,
            node_share=round(charge / (sum(by_space.values()) + idle_charge), 3)
            if by_space
            else 0.0,
            charge=round(charge, 2),
        )
        for space, charge in sorted(by_space.items())
    ]
    return lines, round(idle_charge, 2)


def rendered(store: Store, hourly: dict[str, int], hours: int = 24) -> str:
    lines, idle = split_bill(store, hourly, hours)
    out = io.StringIO()
    out.write("namespace    charge   share\n")
    for line in lines:
        out.write(
            f"{line.namespace:<12} {line.charge:<8} {line.node_share:.1%}\n"
        )
    out.write(f"platform-idle {idle}\n")
    return out.getvalue()
