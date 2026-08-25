"""Restart policies: always, on-failure, never, and who each one is for.

A service restarts always, because its job is to exist. A batch task
restarts on failure only, because success is its exit. A migration
restarts never, because running twice is worse than not finishing,
and the operator who reruns it should do so with their name on the
decision. The keeper applies the policy at the moment a task ends and
records what it did, so the answer to why did this come back, or why
did it not, is a lookup instead of an argument.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.store import Store

POLICIES = ("always", "on-failure", "never")


@dataclass
class RestartKeeper:
    policies: dict[str, str] = field(default_factory=dict)
    restarted: int = 0
    left_alone: int = 0
    log: list[str] = field(default_factory=list)

    def assign(self, task_name: str, policy: str) -> None:
        if policy not in POLICIES:
            raise Invalid(f"unknown restart policy {policy}")
        self.policies[task_name] = policy

    def _should_restart(self, policy: str, phase: str) -> bool:
        if policy == "always":
            return True
        if policy == "on-failure":
            return phase == "Failed"
        return False

    def sweep(self, store: Store, now: int) -> list[str]:
        actions = []
        for task in list(store.tasks.values()):
            if task.phase not in ("Succeeded", "Failed"):
                continue
            policy = self.policies.get(task.spec.name)
            if policy is None:
                continue
            if self._should_restart(policy, task.phase):
                generation = task.generation
                was = task.phase
                task.phase = "Pending"
                task.node = None
                task.restarts += 1
                store.update_task(task, read_generation=generation)
                self.restarted += 1
                line = f"[{now}] {task.spec.name} was {was}, {policy} restarts it"
                self.log.append(line)
                actions.append(line)
            else:
                line = (
                    f"{task.spec.name} stays {task.phase}, policy {policy}"
                )
                if line not in self.log:
                    self.left_alone += 1
                    self.log.append(line)
                    actions.append(line)
        return actions
