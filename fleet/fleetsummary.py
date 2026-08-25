"""The fleet summary: capacity, waste, tenants and risk on one page.

The weekly page for the person who owns the bill: totals first, the
two waste gaps with their owners, the top tenants by requested cpu,
the N+1 ruling, and the days-to-full projection per axis. Every number
on the page comes from a module that measured it; the summary adds
only order, and the order is the reader's: money, waste, who, risk.
"""

from __future__ import annotations

import io

from fleet.capacityplan import project, survives_n_plus_one
from fleet.store import Store
from fleet.utilization import survey, totals


def top_tenants(store: Store, count: int = 3) -> list[tuple[str, int]]:
    by_space: dict[str, int] = {}
    for task in store.active_tasks():
        by_space[task.spec.namespace] = (
            by_space.get(task.spec.namespace, 0) + task.spec.needs.cpu
        )
    return sorted(by_space.items(), key=lambda held: (-held[1], held[0]))[:count]


def summary(
    store: Store,
    usage: dict[str, int],
    cpu_growth: float,
    memory_growth: float,
) -> str:
    out = io.StringIO()
    rows = survey(store, usage)
    whole = totals(rows)
    out.write("fleet summary\n")
    out.write("=" * 40 + "\n")
    out.write(
        f"capacity {whole['capacity']}m cpu across {len(rows)} nodes, "
        f"requested {whole['requested']}m, used {whole['used']}m\n"
    )
    out.write(
        f"waste: teams hold {whole['request_gap']}m unused, "
        f"platform strands {whole['allocation_gap']}m unclaimed\n"
    )
    out.write("top tenants:\n")
    for space, cpu in top_tenants(store):
        out.write(f"  {space}: {cpu}m requested\n")
    survives, why = survives_n_plus_one(store)
    out.write(f"n+1: {'ok' if survives else 'AT RISK'}, {why}\n")
    for projection in project(store, cpu_growth, memory_growth):
        out.write(f"growth: {projection.line()}\n")
    return out.getvalue()
