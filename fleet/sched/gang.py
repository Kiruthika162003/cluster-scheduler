"""Gang scheduling: all of the group or none of it, and why half is worse.

A distributed training job needs its eight workers together; four
running and four pending is the worst of both worlds, hoarding capacity
while doing nothing. The naive scheduler admits members one at a time
and two gangs can deadlock, each holding half a cluster and waiting for
the other's half. The gang scheduler simulates the whole admission first
and binds only when every member fits, so the cluster holds finished
placements and free space, never hostages.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Unschedulable
from fleet.objects import Resources, Task, TaskSpec, free
from fleet.sched.core import Scheduler
from fleet.store import Store


@dataclass(frozen=True)
class Gang:
    name: str
    members: int
    each_needs: Resources

    def specs(self) -> list[TaskSpec]:
        return [
            TaskSpec(
                name=f"{self.name}-{ordinal}",
                needs=self.each_needs,
                labels=(("gang", self.name),),
            )
            for ordinal in range(self.members)
        ]


@dataclass
class GangScheduler:
    inner: Scheduler = field(default_factory=Scheduler)
    admitted: int = 0
    refused: int = 0

    def _rehearse(self, store: Store, gang: Gang) -> dict[str, str] | None:
        """Place every member on paper; None when any member is homeless."""
        nodes = sorted(store.nodes.values(), key=lambda node: node.name)
        headroom = {node.name: free(node, store.active_tasks()) for node in nodes}
        placement: dict[str, str] = {}
        for spec in gang.specs():
            home = None
            for node in nodes:
                if spec.needs.fits_in(headroom[node.name]):
                    home = node.name
                    break
            if home is None:
                return None
            headroom[home] = headroom[home].minus(spec.needs)
            placement[spec.name] = home
        return placement

    def admit(self, store: Store, gang: Gang) -> bool:
        placement = self._rehearse(store, gang)
        if placement is None:
            self.refused += 1
            return False
        for spec in gang.specs():
            task = Task(spec=spec)
            store.add_task(task)
            generation = task.generation
            task.bound_to(placement[spec.name])
            store.update_task(task, read_generation=generation)
        self.admitted += 1
        return True


def naive_admit(store: Store, scheduler: Scheduler, gang: Gang) -> int:
    """One member at a time; returns how many landed before the wall."""
    landed = 0
    for spec in gang.specs():
        task = Task(spec=spec)
        store.add_task(task)
        try:
            scheduler.schedule(store, task)
            landed += 1
        except Unschedulable:
            break
    return landed


def hostages(store: Store) -> dict[str, int]:
    """Per gang: bound members of gangs that are not fully bound."""
    by_gang: dict[str, list[Task]] = {}
    for task in store.tasks.values():
        name = task.spec.label_map().get("gang")
        if name is not None:
            by_gang.setdefault(name, []).append(task)
    held = {}
    for name, members in by_gang.items():
        bound = sum(1 for member in members if member.is_active())
        if 0 < bound < len(members):
            held[name] = bound
    return held
