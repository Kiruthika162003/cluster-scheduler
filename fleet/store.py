"""The state store: versioned writes, refused staleness, replayable events.

Controllers read objects, decide, and write back. Two controllers racing
on one object is the normal case, not the exception, so every write
carries the generation the writer read and the store refuses the stale
one. Every accepted write appends an event, and a watcher replays from
any cursor, which is what lets a controller crash and resume without a
special path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Conflict, NotFound
from fleet.objects import Node, Task


@dataclass
class Event:
    sequence: int
    kind: str
    name: str


@dataclass
class Store:
    tasks: dict[str, Task] = field(default_factory=dict)
    nodes: dict[str, Node] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    writes: int = 0
    refused: int = 0

    def _record(self, kind: str, name: str) -> None:
        self.events.append(Event(sequence=len(self.events), kind=kind, name=name))
        self.writes += 1

    def add_task(self, task: Task) -> None:
        if task.spec.name in self.tasks:
            raise Conflict(f"task {task.spec.name} exists")
        self.tasks[task.spec.name] = task
        self._record("task-added", task.spec.name)

    def get_task(self, name: str) -> Task:
        if name not in self.tasks:
            raise NotFound(f"task {name}")
        return self.tasks[name]

    def update_task(self, task: Task, read_generation: int) -> None:
        held = self.get_task(task.spec.name)
        if held.generation != read_generation:
            self.refused += 1
            raise Conflict(
                f"task {task.spec.name} moved: {held.generation} != {read_generation}"
            )
        task.generation = read_generation + 1
        self.tasks[task.spec.name] = task
        self._record("task-updated", task.spec.name)


    def batch_update(self, updates: list[tuple]) -> None:
        """Apply every (task, read_generation) update or none of them.

        The batch validates every generation before writing anything, so
        a Conflict raised for the third update cannot leave the first two
        applied: half-applied batches are the storage bug wearing a
        controller costume.
        """
        for task, read_generation in updates:
            held = self.get_task(task.spec.name)
            if held.generation != read_generation:
                self.refused += 1
                raise Conflict(
                    f"batch: {task.spec.name} moved: "
                    f"{held.generation} != {read_generation}"
                )
        for task, read_generation in updates:
            task.generation = read_generation + 1
            self.tasks[task.spec.name] = task
            self._record("task-updated", task.spec.name)

    def remove_task(self, name: str) -> None:
        if name not in self.tasks:
            raise NotFound(f"task {name}")
        del self.tasks[name]
        self._record("task-removed", name)

    def add_node(self, node: Node) -> None:
        if node.name in self.nodes:
            raise Conflict(f"node {node.name} exists")
        self.nodes[node.name] = node
        self._record("node-added", node.name)

    def get_node(self, name: str) -> Node:
        if name not in self.nodes:
            raise NotFound(f"node {name}")
        return self.nodes[name]

    def remove_node(self, name: str) -> None:
        if name not in self.nodes:
            raise NotFound(f"node {name}")
        del self.nodes[name]
        self._record("node-removed", name)

    def active_tasks(self) -> list[Task]:
        return [task for task in self.tasks.values() if task.is_active()]

    def pending_tasks(self) -> list[Task]:
        return [task for task in self.tasks.values() if task.phase == "Pending"]

    def since(self, cursor: int) -> list[Event]:
        return self.events[cursor:]
