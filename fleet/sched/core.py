"""The scheduler: filter every node, score the survivors, bind the best.

One task at a time, deterministically: ties break on node name so a
replayed cluster schedules identically. The refusals are kept and
returned in the Unschedulable error, because a scheduler that cannot
say why is a scheduler that cannot be argued with.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Unschedulable
from fleet.objects import Node, Task
from fleet.sched.filters import EVERY_FILTER
from fleet.store import Store


@dataclass
class Scheduler:
    scorers: tuple = ()
    placed: int = 0
    rejected: int = 0
    reasons_kept: dict[str, dict[str, str]] = field(default_factory=dict)

    def feasible(
        self, task: Task, nodes: list[Node], active: list[Task]
    ) -> tuple[list[Node], dict[str, str]]:
        passing = []
        reasons: dict[str, str] = {}
        for node in nodes:
            refusal = None
            for check in EVERY_FILTER:
                refusal = check(task, node, active)
                if refusal is not None:
                    break
            if refusal is None:
                passing.append(node)
            else:
                reasons[node.name] = refusal
        return passing, reasons

    def pick(self, task: Task, passing: list[Node], active: list[Task]) -> Node:
        def total(node: Node) -> float:
            return sum(score(task, node, active) for score in self.scorers)

        return max(sorted(passing, key=lambda node: node.name), key=total)

    def schedule(self, store: Store, task: Task) -> Node:
        nodes = sorted(store.nodes.values(), key=lambda node: node.name)
        active = store.active_tasks()
        passing, reasons = self.feasible(task, nodes, active)
        if not passing:
            self.rejected += 1
            self.reasons_kept[task.spec.name] = reasons
            raise Unschedulable(reasons)
        chosen = self.pick(task, passing, active)
        generation = task.generation
        task.bound_to(chosen.name)
        store.update_task(task, read_generation=generation)
        self.placed += 1
        return chosen

    def schedule_pending(self, store: Store) -> tuple[int, int]:
        """Schedule every pending task once; (placed, stuck) this pass."""
        placed = stuck = 0
        queue = sorted(
            store.pending_tasks(), key=lambda t: (-t.spec.priority, t.spec.name)
        )
        for task in queue:
            try:
                self.schedule(store, task)
                placed += 1
            except Unschedulable:
                stuck += 1
        return placed, stuck
