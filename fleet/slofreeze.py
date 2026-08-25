"""The budget freeze: a bankrupt error budget stops the release train.

The maintenance calendar freezes changes by the clock; this gate
freezes them by behaviour. A deploy whose SLO budget is exhausted
may not roll until the budget recovers or someone breaks the glass,
and breaking the glass requires a name and a reason because the
override is the part the postmortem reads. Denials are counted per
deploy so the report can show how often the brake actually engaged,
which is the number that settles the argument about whether the
policy has teeth or is theatre.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.slo import SloBoard


@dataclass(frozen=True)
class Glass:
    deploy: str
    who: str
    reason: str
    at: int


@dataclass
class SloFreezeGate:
    board: SloBoard
    broken: dict[str, Glass] = field(default_factory=dict)
    denials: dict[str, int] = field(default_factory=dict)

    def break_glass(self, deploy: str, who: str, reason: str, now: int) -> Glass:
        glass = Glass(deploy=deploy, who=who, reason=reason, at=now)
        self.broken[deploy] = glass
        return glass

    def may_ship(self, deploy: str) -> tuple[bool, str]:
        frozen = deploy in self.board.frozen_deploys()
        if not frozen:
            self.broken.pop(deploy, None)
            return True, "budget healthy"
        if deploy in self.broken:
            glass = self.broken[deploy]
            return True, f"glass broken by {glass.who}: {glass.reason}"
        self.denials[deploy] = self.denials.get(deploy, 0) + 1
        return False, "error budget exhausted"

    def step(self, roller, store, roll) -> str:
        allowed, why = self.may_ship(roll.name)
        if not allowed:
            return f"frozen: {why}"
        return roller.step(store, roll)

    def report(self) -> str:
        lines = [
            f"{len(self.board.frozen_deploys())} frozen, "
            f"{len(self.broken)} glasses broken"
        ]
        for deploy in sorted(self.denials):
            lines.append(f"  {deploy}: {self.denials[deploy]} rolls refused")
        for deploy in sorted(self.broken):
            glass = self.broken[deploy]
            lines.append(
                f"  {deploy}: shipping on broken glass "
                f"({glass.who}: {glass.reason})"
            )
        return "\n".join(lines)
