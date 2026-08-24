"""Ordinal sets: stable names, ordered birth, reverse retirement.

A stateful task's name is its identity: ordinal-0 owns the first data
slice forever, so the set never renames survivors the way a deployment
happily would. Birth is ordered, each ordinal waiting for its
predecessor to run before starting, because replicated stores bootstrap
from their elders; retirement is the exact reverse. An update replaces
one ordinal at a time from the top, and a replacement keeps the name,
which is the entire point of having one.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from fleet.objects import Task, TaskSpec
from fleet.store import Store


@dataclass(frozen=True)
class OrdinalSpec:
    name: str
    count: int
    template: TaskSpec
    revision: int = 1

    def child_name(self, ordinal: int) -> str:
        return f"{self.name}-{ordinal}"


@dataclass
class OrdinalKeeper:
    created: int = 0
    replaced: int = 0
    log: list[str] = field(default_factory=list)

    def _stamped(self, spec: OrdinalSpec, ordinal: int) -> TaskSpec:
        labels = dict(spec.template.labels)
        labels["set"] = spec.name
        labels["revision"] = str(spec.revision)
        return replace(
            spec.template,
            name=spec.child_name(ordinal),
            labels=tuple(sorted(labels.items())),
        )

    def _revision_of(self, task: Task) -> int:
        return int(task.spec.label_map().get("revision", "0"))

    def reconcile(self, store: Store, spec: OrdinalSpec) -> str:
        """One ordered step per call: create, retire, or replace exactly one."""
        for ordinal in range(spec.count):
            name = spec.child_name(ordinal)
            held = store.tasks.get(name)
            if held is None:
                if ordinal > 0:
                    elder = store.tasks.get(spec.child_name(ordinal - 1))
                    if elder is None or elder.phase != "Running":
                        return f"waiting on {spec.child_name(ordinal - 1)}"
                store.add_task(Task(spec=self._stamped(spec, ordinal)))
                self.created += 1
                self.log.append(f"born {name}")
                return f"born {name}"
            if not held.is_active() and held.phase != "Pending":
                store.remove_task(name)
                store.add_task(Task(spec=self._stamped(spec, ordinal)))
                self.log.append(f"reborn {name}")
                return f"reborn {name}"
        for ordinal in range(spec.count - 1, -1, -1):
            name = spec.child_name(ordinal)
            held = store.tasks.get(name)
            if held is not None and self._revision_of(held) != spec.revision:
                if held.phase == "Running":
                    store.remove_task(name)
                    store.add_task(Task(spec=self._stamped(spec, ordinal)))
                    self.replaced += 1
                    self.log.append(f"replaced {name} at r{spec.revision}")
                    return f"replaced {name}"
                return f"waiting on {name}"
        stragglers = sorted(
            (
                task.spec.name
                for task in store.tasks.values()
                if task.spec.label_map().get("set") == spec.name
                and int(task.spec.name.rsplit("-", 1)[1]) >= spec.count
            ),
            reverse=True,
        )
        if stragglers:
            store.remove_task(stragglers[0])
            self.log.append(f"retired {stragglers[0]}")
            return f"retired {stragglers[0]}"
        return "settled"
