"""Live migration: copy the memory while it changes, cut over when it stops.

Moving a running task without killing it is a race between the copy
and the workload dirtying what was copied. Pre-copy rounds transfer
the pages dirtied since the last round; each round should shrink if
the workload's write rate is below the link's copy rate. The cutover
decision is arithmetic, not hope: when the remaining dirty set can
transfer inside the pause budget, pause and finish; when rounds stop
shrinking, the migration will never converge and the verdict says
so plainly. The tests found the sharp version of that edge: at
near-parity rates the ceiling-rounded round time stops shrinking,
the dirty set re-fills exactly, and the stall is detected in three
rounds rather than crawling toward a cap. The receipt records every
round, because
"it took 6 rounds and a 40ms pause" is tuning data and "it migrated"
is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass(frozen=True)
class Round:
    number: int
    copied: int
    remaining_dirty: int
    ticks: int


@dataclass
class MigrationPlan:
    memory: int
    dirty_rate: int
    copy_rate: int
    pause_budget: int
    max_rounds: int = 10

    def __post_init__(self) -> None:
        if min(self.memory, self.copy_rate) <= 0 or self.dirty_rate < 0:
            raise Invalid("memory and copy_rate must be positive")
        if self.pause_budget <= 0:
            raise Invalid("a zero pause budget forbids any cutover")


@dataclass
class Migration:
    plan: MigrationPlan
    rounds: list[Round] = field(default_factory=list)
    verdict: str = "pending"
    pause_ticks: int = 0

    def run(self) -> str:
        dirty = self.plan.memory
        for number in range(1, self.plan.max_rounds + 1):
            ticks = -(-dirty // self.plan.copy_rate)
            if ticks <= self.plan.pause_budget:
                self.pause_ticks = ticks
                self.rounds.append(
                    Round(
                        number=number,
                        copied=dirty,
                        remaining_dirty=0,
                        ticks=ticks,
                    )
                )
                self.verdict = (
                    f"cut over after {number} rounds with a "
                    f"{ticks}-tick pause"
                )
                return self.verdict
            redirtied = min(dirty, ticks * self.plan.dirty_rate)
            self.rounds.append(
                Round(
                    number=number,
                    copied=dirty,
                    remaining_dirty=redirtied,
                    ticks=ticks,
                )
            )
            if redirtied >= dirty:
                self.verdict = (
                    "will never converge: the workload dirties faster "
                    "than the link copies; throttle it or give up"
                )
                return self.verdict
            dirty = redirtied
        self.verdict = (
            f"gave up after {self.plan.max_rounds} rounds with "
            f"{dirty} still dirty"
        )
        return self.verdict

    def downtime(self) -> int:
        if not self.verdict.startswith("cut over"):
            raise Invalid("no cutover happened")
        return self.pause_ticks

    def receipt(self) -> str:
        lines = [self.verdict]
        for entry in self.rounds:
            lines.append(
                f"  round {entry.number}: copied {entry.copied} in "
                f"{entry.ticks} ticks, {entry.remaining_dirty} redirtied"
            )
        return "\n".join(lines)


def migrate_or_explain(
    memory: int, dirty_rate: int, copy_rate: int, pause_budget: int
) -> Migration:
    migration = Migration(
        plan=MigrationPlan(
            memory=memory,
            dirty_rate=dirty_rate,
            copy_rate=copy_rate,
            pause_budget=pause_budget,
        )
    )
    migration.run()
    return migration
