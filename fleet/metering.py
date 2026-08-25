"""Usage metering: integrals, because bills are areas under curves.

The meter samples the store once a tick and accumulates cpu-ticks per
namespace, running tasks only, since Pending work consumes nothing but
patience. The statement renders each namespace's integral alongside its
share, and the reconciliation check that the shares sum to one is in
the tests because a bill that does not add up is two bugs, one in the
math and one in the trust.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from fleet.store import Store


@dataclass
class Meter:
    cpu_ticks: dict[str, int] = field(default_factory=dict)
    task_ticks: dict[str, int] = field(default_factory=dict)
    samples: int = 0

    def sample(self, store: Store) -> None:
        self.samples += 1
        for task in store.tasks.values():
            if task.phase != "Running":
                continue
            space = task.spec.namespace
            self.cpu_ticks[space] = (
                self.cpu_ticks.get(space, 0) + task.spec.needs.cpu
            )
            self.task_ticks[space] = self.task_ticks.get(space, 0) + 1

    def total_cpu_ticks(self) -> int:
        return sum(self.cpu_ticks.values())

    def share_of(self, namespace: str) -> float:
        total = self.total_cpu_ticks()
        if total == 0:
            return 0.0
        return self.cpu_ticks.get(namespace, 0) / total

    def statement(self) -> str:
        out = io.StringIO()
        out.write(
            f"usage statement over {self.samples} ticks\n"
        )
        out.write("namespace    cpu_ticks  task_ticks  share\n")
        for space in sorted(self.cpu_ticks):
            out.write(
                f"{space:<12} {self.cpu_ticks[space]:<10} "
                f"{self.task_ticks.get(space, 0):<11} "
                f"{self.share_of(space):.1%}\n"
            )
        if not self.cpu_ticks:
            out.write("nothing ran\n")
        return out.getvalue()
