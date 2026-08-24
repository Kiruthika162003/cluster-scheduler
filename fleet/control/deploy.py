"""The deployment controller: converge the count, never guess the world.

A deployment says how many replicas of a template should exist. The
controller reads what exists, computes the difference, and does the
smallest thing: create the missing, delete the surplus newest-first,
adopt matching orphans instead of duplicating them. It runs from the
store's events, so a crashed controller resumes by reading, not by
remembering.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from fleet.errors import NotFound
from fleet.objects import Task, TaskSpec
from fleet.store import Store


@dataclass(frozen=True)
class DeploySpec:
    name: str
    replicas: int
    template: TaskSpec

    def child_name(self, ordinal: int) -> str:
        return f"{self.name}-{ordinal}"


@dataclass
class Deployer:
    created: int = 0
    deleted: int = 0
    adopted: int = 0
    owned: dict[str, set[str]] = field(default_factory=dict)

    def _children(self, store: Store, spec: DeploySpec) -> list[Task]:
        mine = []
        for task in store.tasks.values():
            if task.spec.label_map().get("deploy") == spec.name and task.phase not in (
                "Succeeded",
                "Failed",
            ):
                mine.append(task)
        return sorted(mine, key=lambda task: task.spec.name)

    def _stamped(self, spec: DeploySpec, ordinal: int) -> TaskSpec:
        labels = dict(spec.template.labels)
        labels["deploy"] = spec.name
        return replace(
            spec.template,
            name=spec.child_name(ordinal),
            labels=tuple(sorted(labels.items())),
        )

    def reconcile(self, store: Store, spec: DeploySpec) -> tuple[int, int]:
        """One pass; returns (created, deleted)."""
        children = self._children(store, spec)
        held = self.owned.setdefault(spec.name, set())
        for child in children:
            if child.spec.name not in held:
                held.add(child.spec.name)
                self.adopted += 1
        created = deleted = 0
        ordinal = 0
        while len(children) + created < spec.replicas:
            name = spec.child_name(ordinal)
            try:
                store.get_task(name)
            except NotFound:
                store.add_task(Task(spec=self._stamped(spec, ordinal)))
                held.add(name)
                self.created += 1
                created += 1
            ordinal += 1
        surplus = len(children) - spec.replicas
        for child in reversed(children):
            if surplus <= 0:
                break
            store.remove_task(child.spec.name)
            held.discard(child.spec.name)
            self.deleted += 1
            deleted += 1
            surplus -= 1
        return created, deleted

    def converged(self, store: Store, spec: DeploySpec) -> bool:
        return len(self._children(store, spec)) == spec.replicas
