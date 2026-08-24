"""Daemon sets: one task per node, following the fleet wherever it goes.

A daemon belongs to every node the way a deployment belongs to a count.
The controller's difference list is computed against nodes, not
replicas: a joining node is missing its daemon, a leaving node strands
one, and a cordoned node keeps its daemon because cordons stop
scheduling of new work, not the machinery that tends the machine. The
daemon binds directly to its node, skipping the scheduler, since there
is no placement decision to make about a task whose home is its name.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from fleet.objects import Task, TaskSpec
from fleet.store import Store


@dataclass(frozen=True)
class DaemonSpec:
    name: str
    template: TaskSpec

    def child_name(self, node_name: str) -> str:
        return f"{self.name}-{node_name}"


@dataclass
class DaemonKeeper:
    created: int = 0
    removed: int = 0
    log: list[str] = field(default_factory=list)

    def _stamped(self, spec: DaemonSpec, node_name: str) -> TaskSpec:
        labels = dict(spec.template.labels)
        labels["daemon"] = spec.name
        return replace(
            spec.template,
            name=spec.child_name(node_name),
            labels=tuple(sorted(labels.items())),
        )

    def reconcile(self, store: Store, spec: DaemonSpec) -> tuple[int, int]:
        wanted = {spec.child_name(name): name for name in store.nodes}
        held = {
            task.spec.name
            for task in store.tasks.values()
            if task.spec.label_map().get("daemon") == spec.name
        }
        created = removed = 0
        for child, node_name in sorted(wanted.items()):
            if child in held:
                continue
            task = Task(spec=self._stamped(spec, node_name))
            store.add_task(task)
            generation = task.generation
            task.bound_to(node_name)
            store.update_task(task, read_generation=generation)
            self.created += 1
            created += 1
            self.log.append(f"{child} follows {node_name}")
        for child in sorted(held - set(wanted)):
            store.remove_task(child)
            self.removed += 1
            removed += 1
            self.log.append(f"{child} stranded, removed")
        return created, removed
