"""Workload identity: the task proves who it is without carrying a password.

Identity is derived, never stored: a task's name is namespace slash
service slash node, minted by the platform at bind time, expiring
fast, and verified against the store's live truth. A stolen document
therefore ages out in ticks, and a document naming a task that no
longer runs where it claims fails verification even before it
expires, because the store outranks the paper. Policies authorize
identities, not addresses, which is the entire point: the address is
whoever got there first, the identity is who the platform placed.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleet.errors import Invalid
from fleet.store import Store

LIFETIME = 20


@dataclass(frozen=True)
class IdentityDocument:
    namespace: str
    service: str
    node: str
    minted_at: int

    def name(self) -> str:
        return f"{self.namespace}/{self.service}@{self.node}"

    def expired(self, now: int) -> bool:
        return now - self.minted_at >= LIFETIME


def mint(store: Store, task_name: str, now: int) -> IdentityDocument:
    task = store.get_task(task_name)
    if not task.is_active() or task.node is None:
        raise Invalid(f"{task_name} is not placed; identity needs a home")
    return IdentityDocument(
        namespace=task.spec.namespace,
        service=task.spec.label_map().get("app", task.spec.name),
        node=task.node,
        minted_at=now,
    )


def verify(
    store: Store, document: IdentityDocument, task_name: str, now: int
) -> tuple[bool, str]:
    if document.expired(now):
        return False, f"document expired, minted {now - document.minted_at} ago"
    task = store.tasks.get(task_name)
    if task is None or not task.is_active():
        return False, f"{task_name} no longer runs"
    if task.node != document.node:
        return False, (
            f"document says {document.node}, the store says {task.node}"
        )
    if task.spec.namespace != document.namespace:
        return False, "namespace mismatch"
    return True, f"verified as {document.name()}"
