"""Sagas: a half-done operation is worse than either whole state.

A node decommission is four steps with side effects: cordon, drain,
snapshot, remove. Dying after the drain leaves a cordoned, empty,
still-billed node that no dashboard explains. The saga runs steps
forward and, on any failure, runs each completed step's
compensation in reverse order, because compensations undo in the
opposite order effects were made for the same reason socks come
off after shoes. Compensations must be idempotent since the saga
may crash mid-undo and re-run; the ledger records every forward
step, the failure, and every backward step, so the postmortem
reads as a story rather than a diff. A step with no compensation
declares it, and the saga refuses to start past the last such
point of no return unless told the caller accepts it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass(frozen=True)
class Step:
    name: str
    act: Callable[[], bool]
    compensate: Callable[[], None] | None = None


@dataclass
class Saga:
    name: str
    steps: list[Step]
    accepts_no_return: bool = False
    ledger: list[str] = field(default_factory=list)
    outcome: str = "not started"

    def __post_init__(self) -> None:
        if not self.steps:
            raise Invalid("a saga needs steps")
        irreversible = [
            step.name for step in self.steps[:-1] if step.compensate is None
        ]
        if irreversible and not self.accepts_no_return:
            raise Invalid(
                f"{', '.join(irreversible)} cannot be compensated and is "
                f"not last; pass accepts_no_return=True to proceed anyway"
            )

    def run(self) -> str:
        done: list[Step] = []
        for step in self.steps:
            if step.act():
                self.ledger.append(f"did {step.name}")
                done.append(step)
                continue
            self.ledger.append(f"FAILED {step.name}")
            self._unwind(done)
            self.outcome = f"failed at {step.name}, unwound {len(done)} steps"
            return self.outcome
        self.outcome = f"completed all {len(done)} steps"
        return self.outcome

    def _unwind(self, done: list[Step]) -> None:
        for step in reversed(done):
            if step.compensate is None:
                self.ledger.append(
                    f"cannot undo {step.name}: past the point of no return"
                )
                continue
            step.compensate()
            self.ledger.append(f"undid {step.name}")

    def story(self) -> str:
        lines = [f"{self.name}: {self.outcome}"]
        lines.extend(f"  {line}" for line in self.ledger)
        return "\n".join(lines)
