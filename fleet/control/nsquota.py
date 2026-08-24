"""Namespace quotas: admission refuses at the door, with the ledger shown.

A namespace's quota caps task count and total requested resources.
Admission is checked at add time against what the namespace already
holds, and a refusal names the axis that ran out and the numbers on
both sides, because a quota error without the arithmetic is a support
ticket. Deleting a task refunds its charge automatically since usage is
computed from the store, never tracked in a side ledger that can drift.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleet.errors import Invalid
from fleet.objects import Resources, Task
from fleet.store import Store


@dataclass(frozen=True)
class NamespaceQuota:
    namespace: str
    max_tasks: int
    max_requests: Resources


@dataclass
class Admission:
    quotas: dict[str, NamespaceQuota]
    admitted: int = 0
    refused: int = 0

    def usage(self, store: Store, namespace: str) -> tuple[int, Resources]:
        count = 0
        total = Resources.none()
        for task in store.tasks.values():
            if task.spec.namespace != namespace:
                continue
            if task.phase in ("Succeeded", "Failed"):
                continue
            count += 1
            total = total.plus(task.spec.needs)
        return count, total

    def check(self, store: Store, task: Task) -> str | None:
        quota = self.quotas.get(task.spec.namespace)
        if quota is None:
            return None
        count, total = self.usage(store, task.spec.namespace)
        if count + 1 > quota.max_tasks:
            return (
                f"{task.spec.namespace}: {count} of {quota.max_tasks} tasks used"
            )
        after = total.plus(task.spec.needs)
        if not after.fits_in(quota.max_requests):
            return (
                f"{task.spec.namespace}: requests {after.cpu}m/{after.memory}Mi "
                f"exceed {quota.max_requests.cpu}m/{quota.max_requests.memory}Mi"
            )
        return None

    def admit(self, store: Store, task: Task) -> None:
        refusal = self.check(store, task)
        if refusal is not None:
            self.refused += 1
            raise Invalid(refusal)
        store.add_task(task)
        self.admitted += 1
