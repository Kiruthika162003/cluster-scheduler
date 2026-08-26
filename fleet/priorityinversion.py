"""Priority inversion: the critical task waits behind the batch task's lock.

A critical task blocks on a resource a scavenger holds while normal
work preempts the scavenger, and the critical task now runs at
scavenger speed. The detector walks the wait edges and flags every
case where a waiter outranks its holder by a full band, with the
chain rendered in rank order because the middle task, the one
preempting the scavenger, is the invisible villain of every
inversion story. The fix is inheritance: while the inversion holds,
the holder borrows the waiter's priority so nothing between the two
bands can preempt it, and the loan is returned the moment the
resource is released, both movements journaled.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.sched.classes import class_of


@dataclass(frozen=True)
class Inversion:
    waiter: str
    holder: str
    resource: str
    waiter_priority: int
    holder_priority: int

    def line(self) -> str:
        return (
            f"{self.waiter} ({class_of(self.waiter_priority)}) waits on "
            f"{self.resource} held by {self.holder} "
            f"({class_of(self.holder_priority)})"
        )


@dataclass
class InversionGuard:
    priorities: dict[str, int] = field(default_factory=dict)
    base_priorities: dict[str, int] = field(default_factory=dict)
    holding: dict[str, str] = field(default_factory=dict)
    waiting: dict[str, tuple[str, str]] = field(default_factory=dict)
    journal: list[str] = field(default_factory=list)

    def track(self, task: str, priority: int) -> None:
        self.priorities[task] = priority
        self.base_priorities[task] = priority

    def acquires(self, task: str, resource: str) -> None:
        if resource in self.holding.values():
            raise Invalid(f"{resource} is already held")
        self.holding[task] = resource

    def blocks_on(self, waiter: str, resource: str) -> None:
        holder = self._holder_of(resource)
        if holder is None:
            raise Invalid(f"nothing holds {resource}")
        self.waiting[waiter] = (resource, holder)

    def _holder_of(self, resource: str) -> str | None:
        for task, held in self.holding.items():
            if held == resource:
                return task
        return None

    def inversions(self) -> list[Inversion]:
        found = []
        for waiter, (resource, holder) in sorted(self.waiting.items()):
            waiter_priority = self.priorities[waiter]
            holder_priority = self.priorities[holder]
            if class_of(waiter_priority) != class_of(holder_priority) and (
                waiter_priority > holder_priority
            ):
                found.append(
                    Inversion(
                        waiter=waiter,
                        holder=holder,
                        resource=resource,
                        waiter_priority=waiter_priority,
                        holder_priority=holder_priority,
                    )
                )
        return found

    def inherit(self, now: int) -> list[str]:
        actions = []
        for inversion in self.inversions():
            if self.priorities[inversion.holder] < inversion.waiter_priority:
                self.priorities[inversion.holder] = inversion.waiter_priority
                line = (
                    f"[{now}] {inversion.holder} inherits priority "
                    f"{inversion.waiter_priority} from {inversion.waiter}"
                )
                self.journal.append(line)
                actions.append(line)
        return actions

    def releases(self, task: str, now: int) -> None:
        resource = self.holding.pop(task, None)
        if resource is None:
            raise Invalid(f"{task} holds nothing")
        for waiter in sorted(self.waiting):
            if self.waiting[waiter][0] == resource:
                del self.waiting[waiter]
        base = self.base_priorities[task]
        if self.priorities[task] != base:
            self.priorities[task] = base
            self.journal.append(
                f"[{now}] {task} returns its borrowed priority, back to {base}"
            )

    def preemptable_by(self, task: str, aggressor_priority: int) -> bool:
        """The whole point: an inherited priority shields the holder."""
        return aggressor_priority > self.priorities.get(task, 0)
