"""The overload valve: the store protects itself before it drowns.

Caps on total objects and on tasks per namespace, checked at the
door with the arithmetic in the refusal. The valve exists for the
runaway client, the retry loop stuck on create, the script with the
off-by-a-thousand, because a control plane that accepts unbounded
objects is a control plane whose next incident is itself. Deletes are
always accepted; the way out of an overload must never be gated by
the overload.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.objects import Task
from fleet.store import Store


@dataclass
class OverloadValve:
    max_objects: int
    max_tasks_per_namespace: int
    refusals: list[str] = field(default_factory=list)

    def admit_task(self, store: Store, task: Task) -> None:
        total = len(store.tasks) + len(store.nodes)
        if total >= self.max_objects:
            refusal = (
                f"store holds {total} objects, the valve closes at "
                f"{self.max_objects}"
            )
            self.refusals.append(refusal)
            raise Invalid(refusal)
        namespace = task.spec.namespace
        held = sum(
            1
            for existing in store.tasks.values()
            if existing.spec.namespace == namespace
        )
        if held >= self.max_tasks_per_namespace:
            refusal = (
                f"{namespace} holds {held} tasks, the valve closes at "
                f"{self.max_tasks_per_namespace}"
            )
            self.refusals.append(refusal)
            raise Invalid(refusal)
        store.add_task(task)

    def pressure(self, store: Store) -> str:
        total = len(store.tasks) + len(store.nodes)
        share = total / self.max_objects if self.max_objects else 1.0
        if share < 0.7:
            return f"calm: {total} of {self.max_objects}"
        if share < 0.9:
            return f"warming: {total} of {self.max_objects}"
        return f"NEAR THE VALVE: {total} of {self.max_objects}"
