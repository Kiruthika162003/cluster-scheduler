"""Scaling rules: the autoscaler's reflexes get a speed limit and a memory.

The replica scaler in autoscale.py answers how many; these rules
answer how fast and how soon. Scale-up is limited to a step per
decision so one metrics spike cannot double the fleet, and scale-down
waits out a stabilization window: the target must have stayed low
for the whole window before a single replica leaves, because load
that returns two ticks after a scale-down pays the cold-start tax
with interest. The two directions are deliberately asymmetric, up
fast and down slow, which is the shape of every good reflex around
capacity. Every decision records what it wanted, what it did, and
which rule bent it, so the graph of desired versus applied is
readable after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass(frozen=True)
class Decision:
    tick: int
    current: int
    desired: int
    applied: int
    rule: str


@dataclass
class ScaleRules:
    max_step_up: int = 4
    stabilization: int = 10
    floor: int = 1
    ceiling: int = 100
    low_since: int | None = None
    decisions: list[Decision] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.floor < 0 or self.ceiling < self.floor:
            raise Invalid("floor and ceiling must make an interval")

    def decide(self, tick: int, current: int, desired: int) -> int:
        clamped = max(self.floor, min(self.ceiling, desired))
        if clamped > current:
            self.low_since = None
            step_limited = min(clamped, current + self.max_step_up)
            rule = (
                "step limit" if step_limited < clamped else (
                    "ceiling" if clamped < desired else "as asked"
                )
            )
            return self._record(tick, current, desired, step_limited, rule)
        if clamped < current:
            if self.low_since is None:
                self.low_since = tick
            waited = tick - self.low_since
            if waited < self.stabilization:
                return self._record(
                    tick,
                    current,
                    desired,
                    current,
                    f"stabilizing ({self.stabilization - waited} to go)",
                )
            return self._record(
                tick,
                current,
                desired,
                clamped,
                "floor" if clamped > desired else "stabilized down",
            )
        self.low_since = None
        return self._record(tick, current, desired, current, "steady")

    def _record(
        self, tick: int, current: int, desired: int, applied: int, rule: str
    ) -> int:
        self.decisions.append(
            Decision(
                tick=tick,
                current=current,
                desired=desired,
                applied=applied,
                rule=rule,
            )
        )
        return applied

    def bent(self) -> list[Decision]:
        return [
            decision
            for decision in self.decisions
            if decision.applied != decision.desired
        ]

    def chart(self) -> str:
        lines = []
        for decision in self.decisions:
            mark = "" if decision.applied == decision.desired else " *"
            lines.append(
                f"[{decision.tick:>3}] {decision.current} -> "
                f"{decision.applied} (wanted {decision.desired}, "
                f"{decision.rule}){mark}"
            )
        return "\n".join(lines)
