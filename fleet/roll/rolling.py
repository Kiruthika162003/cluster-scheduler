"""Rolling updates: surge, drain, verify, and only then continue.

A rollout replaces old-template tasks with new ones under two limits:
how many extras may exist during the change and how many of the wanted
count may be missing. Each step surges new tasks, waits for them to
report healthy, then retires old ones the budget allows. A step that
cannot finish stops the rollout where it stands, because a stuck rollout
is an incident already and moving further only widens it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from fleet.control.budget import Guard
from fleet.objects import Task, TaskSpec
from fleet.store import Store


@dataclass(frozen=True)
class Rollout:
    name: str
    replicas: int
    template: TaskSpec
    revision: int
    max_surge: int = 1
    max_unavailable: int = 0


@dataclass
class Roller:
    surged: int = 0
    retired: int = 0
    halted: int = 0

    def _mine(self, store: Store, roll: Rollout) -> list[Task]:
        return sorted(
            (
                task
                for task in store.tasks.values()
                if task.spec.label_map().get("deploy") == roll.name
                and task.phase not in ("Succeeded", "Failed")
            ),
            key=lambda task: task.spec.name,
        )

    def _revision_of(self, task: Task) -> int:
        return int(task.spec.label_map().get("revision", "0"))

    def _stamped(self, roll: Rollout, ordinal: int) -> TaskSpec:
        labels = dict(roll.template.labels)
        labels["deploy"] = roll.name
        labels["revision"] = str(roll.revision)
        return replace(
            roll.template,
            name=f"{roll.name}-r{roll.revision}-{ordinal}",
            labels=tuple(sorted(labels.items())),
        )

    def fresh(self, store: Store, roll: Rollout) -> list[Task]:
        return [
            task
            for task in self._mine(store, roll)
            if self._revision_of(task) == roll.revision
        ]

    def stale(self, store: Store, roll: Rollout) -> list[Task]:
        return [
            task
            for task in self._mine(store, roll)
            if self._revision_of(task) != roll.revision
        ]

    def step(self, store: Store, roll: Rollout, guard: Guard | None = None) -> str:
        """One increment; returns what happened: surged, retired, done, stuck."""
        fresh = self.fresh(store, roll)
        stale = self.stale(store, roll)
        healthy_fresh = [task for task in fresh if task.phase == "Running"]
        if not stale and len(healthy_fresh) >= roll.replicas:
            return "done"
        total = len(fresh) + len(stale)
        if len(fresh) < roll.replicas and total < roll.replicas + roll.max_surge:
            ordinal = len(fresh)
            store.add_task(Task(spec=self._stamped(roll, ordinal)))
            self.surged += 1
            return "surged"
        available = len(healthy_fresh) + len(
            [task for task in stale if task.phase == "Running"]
        )
        if stale and available - 1 >= roll.replicas - roll.max_unavailable:
            victim = stale[-1]
            if guard is not None:
                may, _ = guard.may_evict(store, victim.spec.name)
                if not may:
                    self.halted += 1
                    return "stuck"
            store.remove_task(victim.spec.name)
            self.retired += 1
            return "retired"
        self.halted += 1
        return "stuck"
