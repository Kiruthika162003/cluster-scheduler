"""Init stages: the task earns Running one stage at a time, in order.

A staged task declares the steps that must complete before it serves:
migrate, warm, then run. The stage keeper advances exactly one stage
per completion, refuses to skip, records how long each stage took, and
fails the task when a stage exhausts its attempts, with the stage
named, because a task that died in migrate and a task that died in
warm are different tickets that were historically one useless word.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.store import Store


@dataclass(frozen=True)
class Stage:
    name: str
    attempts_allowed: int = 3


@dataclass
class StagedTask:
    task_name: str
    stages: tuple[Stage, ...]
    at: int = 0
    attempts: int = 0
    started_at: dict[str, int] = field(default_factory=dict)
    durations: dict[str, int] = field(default_factory=dict)
    failed_stage: str | None = None

    def current(self) -> Stage | None:
        if self.at >= len(self.stages):
            return None
        return self.stages[self.at]


@dataclass
class StageKeeper:
    staged: dict[str, StagedTask] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)

    def declare(self, task_name: str, stages: tuple[Stage, ...]) -> None:
        if not stages:
            raise Invalid(f"{task_name}: a staged task needs stages")
        self.staged[task_name] = StagedTask(task_name=task_name, stages=stages)

    def begin(self, task_name: str, now: int) -> str:
        held = self.staged[task_name]
        stage = held.current()
        if stage is None:
            raise Invalid(f"{task_name}: no stage to begin")
        held.started_at.setdefault(stage.name, now)
        return stage.name

    def complete(self, store: Store, task_name: str, now: int) -> str:
        held = self.staged[task_name]
        stage = held.current()
        if stage is None:
            raise Invalid(f"{task_name}: nothing in flight")
        held.durations[stage.name] = now - held.started_at.get(stage.name, now)
        held.at += 1
        held.attempts = 0
        self.log.append(f"{task_name}: {stage.name} done in {held.durations[stage.name]}")
        if held.current() is None:
            task = store.get_task(task_name)
            generation = task.generation
            task.phase = "Running"
            store.update_task(task, read_generation=generation)
            return "running"
        return held.current().name

    def fail(self, store: Store, task_name: str, now: int) -> str:
        held = self.staged[task_name]
        stage = held.current()
        if stage is None:
            raise Invalid(f"{task_name}: nothing in flight")
        held.attempts += 1
        if held.attempts >= stage.attempts_allowed:
            held.failed_stage = stage.name
            task = store.get_task(task_name)
            generation = task.generation
            task.phase = "Failed"
            store.update_task(task, read_generation=generation)
            self.log.append(
                f"{task_name}: failed in {stage.name} "
                f"after {held.attempts} attempts at {now}"
            )
            return f"failed in {stage.name}"
        return f"retrying {stage.name}, attempt {held.attempts + 1}"

    def stage_report(self, task_name: str) -> str:
        held = self.staged[task_name]
        parts = [
            f"{stage.name}={held.durations.get(stage.name, '-')}"
            for stage in held.stages
        ]
        tail = f", failed in {held.failed_stage}" if held.failed_stage else ""
        return f"{task_name}: {' '.join(parts)}{tail}"
