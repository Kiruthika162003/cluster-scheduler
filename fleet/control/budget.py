"""Disruption budgets: voluntary evictions ask, involuntary ones apologise.

A budget names a label selector and the minimum count of those tasks
that must stay active. Drains and rollouts consult it and are refused
when the floor would break; node failures do not consult anyone, which
is why the budget's job is to keep enough spread that the involuntary
kind cannot take the floor out either.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.store import Store


@dataclass(frozen=True)
class Budget:
    name: str
    selector_key: str
    selector_value: str
    min_available: int


@dataclass
class Guard:
    budgets: list[Budget] = field(default_factory=list)
    allowed: int = 0
    refused: int = 0

    def _covered_active(self, store: Store, budget: Budget) -> int:
        return sum(
            1
            for task in store.active_tasks()
            if task.spec.label_map().get(budget.selector_key) == budget.selector_value
        )

    def may_evict(self, store: Store, task_name: str) -> tuple[bool, str]:
        task = store.get_task(task_name)
        labels = task.spec.label_map()
        for budget in self.budgets:
            if labels.get(budget.selector_key) != budget.selector_value:
                continue
            active = self._covered_active(store, budget)
            if task.is_active() and active - 1 < budget.min_available:
                self.refused += 1
                return False, (
                    f"budget {budget.name}: {active} active, floor {budget.min_available}"
                )
        self.allowed += 1
        return True, "ok"

    def drain(self, store: Store, node_name: str) -> tuple[list[str], list[str]]:
        """Evict what the budgets allow from a node; (evicted, refused)."""
        evicted: list[str] = []
        refused: list[str] = []
        for task in sorted(store.active_tasks(), key=lambda t: t.spec.name):
            if task.node != node_name:
                continue
            may, _ = self.may_evict(store, task.spec.name)
            if not may:
                refused.append(task.spec.name)
                continue
            generation = task.generation
            task.phase = "Pending"
            task.node = None
            store.update_task(task, read_generation=generation)
            evicted.append(task.spec.name)
        return evicted, refused
