"""Spot nodes: rented cheap, reclaimed on notice, and the work must move.

A spot node can be taken back with a short warning. The reclaim handler
has the notice window to drain what it can; anything still on the node
when the window closes is lost mid-flight and pays its work again. The
meters compare a fleet that reacts to notices with one that ignores
them, in work-ticks lost and reruns, against the rent saved by the
cheaper machines.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.objects import Task
from fleet.store import Store


@dataclass
class Notice:
    node: str
    issued_at: int
    deadline: int


@dataclass
class SpotMarket:
    """Reclaims by schedule; the schedule is the trial's script."""

    reclaims: dict[str, int] = field(default_factory=dict)
    notice_window: int = 4
    notices: list[Notice] = field(default_factory=list)

    def tick(self, now: int) -> list[Notice]:
        fresh = []
        for node, when in self.reclaims.items():
            if when - self.notice_window == now:
                notice = Notice(node=node, issued_at=now, deadline=when)
                self.notices.append(notice)
                fresh.append(notice)
        return fresh

    def reclaimed_now(self, now: int) -> list[str]:
        return [node for node, when in self.reclaims.items() if when == now]


@dataclass
class WorkTracker:
    """Ticks of progress per task; a mid-flight loss pays them again."""

    needed: dict[str, int] = field(default_factory=dict)
    progress: dict[str, int] = field(default_factory=dict)
    lost_ticks: int = 0
    reruns: int = 0
    finished: list[str] = field(default_factory=list)

    def advance(self, store: Store) -> None:
        for task in store.tasks.values():
            name = task.spec.name
            if task.phase != "Running" or name in self.finished:
                continue
            self.progress[name] = self.progress.get(name, 0) + 1
            if self.progress[name] >= self.needed.get(name, 1):
                task.phase = "Succeeded"
                self.finished.append(name)

    def lose(self, task: Task) -> None:
        name = task.spec.name
        dropped = self.progress.get(name, 0)
        self.lost_ticks += dropped
        if dropped:
            self.reruns += 1
        self.progress[name] = 0


def evacuate(store: Store, node: str) -> int:
    """Move everything off a noticed node; progress survives a clean move."""
    moved = 0
    for task in list(store.active_tasks()):
        if task.node != node:
            continue
        generation = task.generation
        task.phase = "Pending"
        task.node = None
        store.update_task(task, read_generation=generation)
        moved += 1
    return moved


def reclaim(store: Store, tracker: WorkTracker, node: str) -> int:
    """The window closed: whatever is still here is lost mid-flight."""
    lost = 0
    for task in list(store.active_tasks()):
        if task.node != node:
            continue
        tracker.lose(task)
        generation = task.generation
        task.phase = "Pending"
        task.node = None
        task.restarts += 1
        store.update_task(task, read_generation=generation)
        lost += 1
    if node in store.nodes:
        store.remove_node(node)
    return lost
