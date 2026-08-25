"""Finalizers: deletion is a request until every janitor signs off.

Deleting an object that owns external things, a volume, a cloud disk,
a DNS record, cannot be one atomic remove: the external cleanup takes
time and can fail. A finalizer is a janitor's signature slot on the
object; deletion marks the object as leaving and it only actually goes
when the last signature clears. An object stuck leaving is not a bug
in the finalizer machinery, it is the machinery pointing at the janitor
who has not finished, by name.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid, NotFound
from fleet.store import Store


@dataclass
class Departures:
    finalizers: dict[str, set[str]] = field(default_factory=dict)
    leaving: dict[str, int] = field(default_factory=dict)
    completed: int = 0

    def protect(self, task_name: str, janitor: str) -> None:
        if task_name in self.leaving:
            raise Invalid(f"{task_name} is already leaving")
        self.finalizers.setdefault(task_name, set()).add(janitor)

    def request_delete(self, store: Store, task_name: str, now: int) -> str:
        if task_name not in store.tasks:
            raise NotFound(f"task {task_name}")
        pending = self.finalizers.get(task_name, set())
        if not pending:
            store.remove_task(task_name)
            self.completed += 1
            return "deleted"
        self.leaving[task_name] = now
        return f"leaving, waiting on {', '.join(sorted(pending))}"

    def clear(self, store: Store, task_name: str, janitor: str) -> str:
        held = self.finalizers.get(task_name, set())
        if janitor not in held:
            raise Invalid(f"{janitor} holds no finalizer on {task_name}")
        held.discard(janitor)
        if not held:
            del self.finalizers[task_name]
            if task_name in self.leaving:
                del self.leaving[task_name]
                store.remove_task(task_name)
                self.completed += 1
                return "deleted"
        return f"cleared {janitor}"

    def stuck(self, now: int, patience: int) -> list[str]:
        return sorted(
            f"{name}: waiting {now - since} on "
            f"{', '.join(sorted(self.finalizers.get(name, set())))}"
            for name, since in self.leaving.items()
            if now - since >= patience
        )
