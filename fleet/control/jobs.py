"""Jobs: run to completion N times, at most M abreast, retries counted.

A deployment maintains a population; a job drains a count. The spec
asks for completions with a parallelism cap and a retry budget per
index. Each completion index is its own little story: it succeeds once,
however many attempts that takes, and the job is done when every index
has succeeded or dead when any index exhausts its budget, because a
job that reports success while an index silently gave up is a batch
system training its users to distrust green.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from fleet.objects import Task, TaskSpec
from fleet.store import Store


@dataclass(frozen=True)
class JobSpec:
    name: str
    completions: int
    parallelism: int
    template: TaskSpec
    retries_per_index: int = 2

    def child_name(self, index: int, attempt: int) -> str:
        return f"{self.name}-i{index}-a{attempt}"


@dataclass
class JobKeeper:
    launched: int = 0
    retried: int = 0
    state: dict[str, dict[int, dict]] = field(default_factory=dict)

    def _index_state(self, spec: JobSpec) -> dict[int, dict]:
        return self.state.setdefault(
            spec.name,
            {
                index: {"succeeded": False, "attempts": 0, "active": None}
                for index in range(spec.completions)
            },
        )

    def _stamped(self, spec: JobSpec, index: int, attempt: int) -> TaskSpec:
        labels = dict(spec.template.labels)
        labels["job"] = spec.name
        labels["index"] = str(index)
        return replace(
            spec.template,
            name=spec.child_name(index, attempt),
            labels=tuple(sorted(labels.items())),
        )

    def reconcile(self, store: Store, spec: JobSpec) -> str:
        """Advance the job one pass; returns running, done, or dead."""
        indexes = self._index_state(spec)
        for held in indexes.values():
            name = held["active"]
            if name is None:
                continue
            task = store.tasks.get(name)
            if task is None or task.phase == "Failed":
                held["active"] = None
                if task is not None:
                    store.remove_task(name)
            elif task.phase == "Succeeded":
                held["succeeded"] = True
                held["active"] = None
                store.remove_task(name)
        if any(
            not held["succeeded"]
            and held["active"] is None
            and held["attempts"] > spec.retries_per_index
            for held in indexes.values()
        ):
            return "dead"
        if all(held["succeeded"] for held in indexes.values()):
            return "done"
        abreast = sum(1 for held in indexes.values() if held["active"] is not None)
        for index in sorted(indexes):
            held = indexes[index]
            if held["succeeded"] or held["active"] is not None:
                continue
            if held["attempts"] > spec.retries_per_index:
                continue
            if abreast >= spec.parallelism:
                break
            attempt = held["attempts"]
            task = Task(spec=self._stamped(spec, index, attempt))
            store.add_task(task)
            held["active"] = task.spec.name
            held["attempts"] += 1
            self.launched += 1
            if attempt > 0:
                self.retried += 1
            abreast += 1
        return "running"
