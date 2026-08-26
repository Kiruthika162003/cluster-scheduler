"""Brownout: shed features in stages so the core survives the surge.

An overloaded service that fails whole is a design choice, and the
wrong one. The ladder orders features from expendable to essential;
rising load sheds from the top, falling load restores from the
bottom, and the two thresholds per stage are deliberately apart so
the boundary has a dead zone: a service at exactly the threshold
must not flap between serving and shedding recommendations twice a
tick. Restores also wait out a hold period at each stage, because
load that dips for two ticks and returns is the same surge taking a
breath. The ledger records every shed and restore with the load
that forced it, which turns "we browned out last night" into a
timeline with numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid

RESTORE_HOLD = 5


@dataclass(frozen=True)
class Stage:
    feature: str
    shed_at: float
    restore_at: float

    def __post_init__(self) -> None:
        if self.restore_at >= self.shed_at:
            raise Invalid(
                f"{self.feature}: restore_at must sit below shed_at "
                f"or the boundary flaps"
            )


@dataclass
class Ladder:
    stages: list[Stage]
    shed: dict[str, int] = field(default_factory=dict)
    calm_since: dict[str, int] = field(default_factory=dict)
    ledger: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        ordered = [stage.shed_at for stage in self.stages]
        if ordered != sorted(ordered):
            raise Invalid("stages must run expendable-first, rising shed_at")

    def observe(self, load: float, now: int) -> list[str]:
        actions = []
        for stage in reversed(self.stages):
            if load >= stage.shed_at and stage.feature not in self.shed:
                self.shed[stage.feature] = now
                self.calm_since.pop(stage.feature, None)
                line = f"[{now}] shed {stage.feature} at load {load:.2f}"
                self.ledger.append(line)
                actions.append(line)
        for stage in self.stages:
            if stage.feature not in self.shed:
                continue
            if load >= stage.restore_at:
                self.calm_since.pop(stage.feature, None)
                continue
            first_calm = self.calm_since.setdefault(stage.feature, now)
            if now - first_calm >= RESTORE_HOLD:
                del self.shed[stage.feature]
                del self.calm_since[stage.feature]
                line = (
                    f"[{now}] restored {stage.feature} at load {load:.2f}"
                )
                self.ledger.append(line)
                actions.append(line)
        return actions

    def serving(self) -> list[str]:
        return [
            stage.feature
            for stage in self.stages
            if stage.feature not in self.shed
        ]

    def mode(self) -> str:
        if not self.shed:
            return "full service"
        kept = self.serving()
        if not kept:
            return "core only"
        return f"browned out: {', '.join(sorted(self.shed))} shed"

    def timeline(self) -> str:
        return "\n".join(self.ledger) if self.ledger else "never browned out"
