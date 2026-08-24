"""Blue green against rolling: the same upgrade, two bills, two rollbacks.

Blue green stands up the whole new fleet beside the old one, cuts
traffic over in one move, and keeps the old fleet warm for instant
rollback. Rolling replaces one at a time inside the same capacity. The
three meters that decide between them: peak capacity held, steps of
exposure where both versions serve, and ticks to undo a bad build
discovered after the switch. Neither wins all three; the meters say
which two you get to pick.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from fleet.objects import Task, TaskSpec
from fleet.store import Store


@dataclass
class BlueGreen:
    replicas: int
    serving: str = "blue"
    peak_tasks: int = 0
    cutovers: int = 0
    log: list[str] = field(default_factory=list)

    def _fleet(self, store: Store, colour: str, template: TaskSpec) -> None:
        for number in range(self.replicas):
            task = Task(
                spec=replace(
                    template,
                    name=f"{colour}-{number}",
                    labels=(("colour", colour),),
                )
            )
            task.bound_to(f"n{number}")
            task.phase = "Running"
            store.add_task(task)
        self.peak_tasks = max(self.peak_tasks, len(store.tasks))

    def deploy_blue(self, store: Store, template: TaskSpec) -> None:
        self._fleet(store, "blue", template)
        self.log.append("blue up, serving")

    def stage_green(self, store: Store, template: TaskSpec) -> None:
        self._fleet(store, "green", template)
        self.log.append("green staged beside blue")

    def cut_over(self) -> None:
        self.serving = "green" if self.serving == "blue" else "blue"
        self.cutovers += 1
        self.log.append(f"cutover, serving {self.serving}")

    def retire_standby(self, store: Store) -> None:
        standby = "blue" if self.serving == "green" else "green"
        for name in [
            task.spec.name
            for task in store.tasks.values()
            if task.spec.label_map().get("colour") == standby
        ]:
            store.remove_task(name)
        self.log.append(f"{standby} retired")

    def rollback_ticks(self) -> int:
        """Undo is one cutover while the standby is still warm."""
        return 1
