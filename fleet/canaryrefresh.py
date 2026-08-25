"""Canary refresh: each replacement proves itself before the next incumbent dies.

The pool refresh replaces iron; burn-in proves iron. Composed, the
refresh becomes cautious: provision the replacement fenced, run its
canaries, and only a graduated node may take its incumbent's place; a
rejected node halts the whole refresh with the rejection in hand,
because a bad node build discovered on replacement three will be on
replacements four through ten as well, and the halt is the cheap
place to learn it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.api import Fleet
from fleet.burnin import BurnIn
from fleet.sched.core import Scheduler


@dataclass
class CanaryRefresh:
    burnin: BurnIn = field(default_factory=lambda: BurnIn(probation=5))
    replaced: list[str] = field(default_factory=list)
    halted_on: str | None = None
    log: list[str] = field(default_factory=list)

    def refresh(
        self,
        fleet: Fleet,
        who: str,
        pool: list[str],
        bad_nodes: set[str] | None = None,
        now: int = 0,
    ) -> str:
        bad = bad_nodes or set()
        clock = now
        for incumbent in pool:
            replacement = f"{incumbent}-next"
            capacity = fleet.store.get_node(incumbent).capacity
            self.burnin.join(fleet.store, replacement, capacity.cpu, clock)
            canary = self.burnin.canary_task(replacement, 0)
            fleet.store.add_task(canary)
            Scheduler().schedule_pending(fleet.store)
            if replacement in bad:
                self.burnin.note_canary_failure(replacement)
            self.burnin.sweep(fleet.store, clock + self.burnin.probation)
            if replacement in self.burnin.rejected:
                self.halted_on = replacement
                self.log.append(
                    f"{replacement} rejected in burn-in, refresh halted"
                )
                return f"halted at {incumbent}"
            for task_name in list(fleet.store.tasks):
                if task_name.startswith(f"canary-{replacement}"):
                    fleet.store.remove_task(task_name)
            fleet.retire_node(who, incumbent)
            fleet.step()
            self.replaced.append(incumbent)
            self.log.append(f"{incumbent} replaced by {replacement}")
            clock += self.burnin.probation + 1
        return "refresh complete"
