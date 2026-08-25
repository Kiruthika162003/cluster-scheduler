"""Taint-based eviction with grace: the tenant may finish its coffee.

A pressure taint lands on a node; tenants that do not tolerate it at
all leave immediately, and tenants with a graced toleration stay for
their stated seconds before going, which is the difference between a
fire alarm and a landlord's notice. The clock starts when the taint
lands, not when the sweeper first looks, so a slow sweeper cannot
extend anyone's lease by being late.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.store import Store


@dataclass(frozen=True)
class GracedToleration:
    key: str
    seconds: int


@dataclass
class TaintEvictor:
    tolerations: dict[str, dict[str, int]] = field(default_factory=dict)
    tainted_at: dict[tuple[str, str], int] = field(default_factory=dict)
    evicted: list[str] = field(default_factory=list)

    def tolerate(self, task_name: str, toleration: GracedToleration) -> None:
        self.tolerations.setdefault(task_name, {})[
            toleration.key
        ] = toleration.seconds

    def taint(self, node_name: str, key: str, now: int) -> None:
        self.tainted_at.setdefault((node_name, key), now)

    def untaint(self, node_name: str, key: str) -> None:
        self.tainted_at.pop((node_name, key), None)

    def sweep(self, store: Store, now: int) -> list[str]:
        leaving = []
        for (node_name, key), since in self.tainted_at.items():
            for task in list(store.active_tasks()):
                if task.node != node_name:
                    continue
                grace = self.tolerations.get(task.spec.name, {}).get(key)
                deadline = since if grace is None else since + grace
                if now >= deadline:
                    generation = task.generation
                    task.phase = "Pending"
                    task.node = None
                    store.update_task(task, read_generation=generation)
                    leaving.append(task.spec.name)
        self.evicted.extend(leaving)
        return sorted(leaving)
