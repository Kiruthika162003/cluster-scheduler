"""The tenancy page: each namespace's usage, quota, and distance to the wall.

Multi-tenant questions arrive namespace-shaped: who is using what, who
is about to hit their quota, who is hoarding requests they do not run.
The page answers all three from the store and the quota table, with the
hoarding column measured as requested-but-not-running, because capacity
reserved by Pending tasks is spent from everyone's cluster and returns
nothing until it schedules.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from fleet.control.nsquota import NamespaceQuota
from fleet.objects import Resources
from fleet.store import Store


@dataclass(frozen=True)
class Row:
    namespace: str
    running: int
    pending: int
    cpu_used: int
    cpu_quota: int | None
    headroom: int | None
    hoarded_cpu: int

    def strained(self) -> bool:
        return self.headroom is not None and self.headroom <= 0


def survey(store: Store, quotas: dict[str, NamespaceQuota]) -> list[Row]:
    seen: dict[str, dict[str, int]] = {}
    for task in store.tasks.values():
        space = task.spec.namespace
        bucket = seen.setdefault(
            space, {"running": 0, "pending": 0, "cpu": 0, "hoard": 0}
        )
        if task.phase in ("Succeeded", "Failed"):
            continue
        bucket["cpu"] += task.spec.needs.cpu
        if task.is_active():
            bucket["running"] += 1
        else:
            bucket["pending"] += 1
            bucket["hoard"] += task.spec.needs.cpu
    rows = []
    for space in sorted(set(seen) | set(quotas)):
        bucket = seen.get(space, {"running": 0, "pending": 0, "cpu": 0, "hoard": 0})
        quota = quotas.get(space)
        cpu_quota = quota.max_requests.cpu if quota else None
        headroom = None if cpu_quota is None else cpu_quota - bucket["cpu"]
        rows.append(
            Row(
                namespace=space,
                running=bucket["running"],
                pending=bucket["pending"],
                cpu_used=bucket["cpu"],
                cpu_quota=cpu_quota,
                headroom=headroom,
                hoarded_cpu=bucket["hoard"],
            )
        )
    return rows


def rendered(store: Store, quotas: dict[str, NamespaceQuota]) -> str:
    out = io.StringIO()
    out.write("namespace   run  pend  cpu_used  quota    headroom  hoarded\n")
    for row in survey(store, quotas):
        quota_text = "-" if row.cpu_quota is None else str(row.cpu_quota)
        headroom_text = "-" if row.headroom is None else str(row.headroom)
        marker = " STRAINED" if row.strained() else ""
        out.write(
            f"{row.namespace:<11} {row.running:<4} {row.pending:<5} "
            f"{row.cpu_used:<9} {quota_text:<8} {headroom_text:<9} "
            f"{row.hoarded_cpu}{marker}\n"
        )
    return out.getvalue()


def quota_map(*quotas: NamespaceQuota) -> dict[str, NamespaceQuota]:
    return {quota.namespace: quota for quota in quotas}


def standard_quota(namespace: str, cpu: int) -> NamespaceQuota:
    return NamespaceQuota(
        namespace=namespace,
        max_tasks=10**6,
        max_requests=Resources(cpu=cpu, memory=10**9),
    )
