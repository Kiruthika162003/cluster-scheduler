"""The descheduler: the rebalancer on a leash made of budgets.

The rebalancer knows which moves consolidate; the guard knows which
evictions the floors permit; the descheduler is the marriage: it asks
the rebalancer for its next move, asks the guard for permission, and
performs only the moves both bless, spending from its own per-run cap.
Every refused move is recorded with who refused it, because a
rebalancer that silently skips protected tasks looks broken to whoever
tuned it, and the record says it is working exactly as leashed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.control.budget import Guard
from fleet.sched.defrag import Rebalancer
from fleet.store import Store


@dataclass
class Descheduler:
    guard: Guard
    per_run_cap: int = 3
    moved: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)

    def run(self, store: Store) -> tuple[int, int]:
        performed = 0
        while performed < self.per_run_cap:
            probe = Rebalancer(budget=1)
            spent = probe.rebalance(store)
            if not spent:
                break
            move = probe.moves[0]
            allowed, why = self.guard.may_evict(store, move.task)
            if not allowed:
                task = store.get_task(move.task)
                generation = task.generation
                task.node = move.source
                store.update_task(task, read_generation=generation)
                self.refused.append(f"{move.task}: {why}")
                break
            self.moved.append(
                f"{move.task}: {move.source} -> {move.target}"
            )
            performed += 1
        return performed, len(self.refused)
