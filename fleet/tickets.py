"""Toil tickets: every manual action is a debt entry with a payoff plan.

When the on-call cordons a node by hand at 3am, the action worked
and the process failed. The ledger records each manual action with
its category, and the arithmetic answers the automation question:
which category costs the most human minutes, and what would a robot
for it be worth. A category crossing the threshold opens an
automation candidate carrying its evidence, and closing one requires
naming the automation that replaced the hands, so the ledger only
shrinks when the work does. The metric that matters is minutes per
week, not tickets, because ten one-minute clicks lose to one
thirty-minute recovery every time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid, NotFound

CANDIDATE_MINUTES = 30


@dataclass(frozen=True)
class Toil:
    tick: int
    actor: str
    category: str
    minutes: int
    note: str


@dataclass
class Candidate:
    category: str
    minutes_seen: int
    opened_at: int
    closed_by: str | None = None


@dataclass
class ToilLedger:
    entries: list[Toil] = field(default_factory=list)
    candidates: dict[str, Candidate] = field(default_factory=dict)

    def log(
        self, tick: int, actor: str, category: str, minutes: int, note: str
    ) -> Candidate | None:
        if minutes <= 0:
            raise Invalid("toil takes time; minutes must be positive")
        self.entries.append(
            Toil(
                tick=tick,
                actor=actor,
                category=category,
                minutes=minutes,
                note=note,
            )
        )
        spent = self.minutes_by()[category]
        open_candidate = self.candidates.get(category)
        if open_candidate is not None and open_candidate.closed_by is None:
            open_candidate.minutes_seen = spent
            return None
        if spent >= CANDIDATE_MINUTES and open_candidate is None:
            candidate = Candidate(
                category=category, minutes_seen=spent, opened_at=tick
            )
            self.candidates[category] = candidate
            return candidate
        return None

    def minutes_by(self) -> dict[str, int]:
        spent: dict[str, int] = {}
        for entry in self.entries:
            spent[entry.category] = spent.get(entry.category, 0) + entry.minutes
        return spent

    def automate(self, category: str, automation: str) -> None:
        candidate = self.candidates.get(category)
        if candidate is None:
            raise NotFound(f"no candidate open for {category}")
        if candidate.closed_by is not None:
            raise Invalid(f"{category} was already automated by {candidate.closed_by}")
        candidate.closed_by = automation

    def worst(self) -> str | None:
        spent = self.minutes_by()
        if not spent:
            return None
        return max(sorted(spent), key=lambda category: spent[category])

    def report(self) -> str:
        spent = self.minutes_by()
        lines = [
            f"{sum(spent.values())} manual minutes across "
            f"{len(self.entries)} actions"
        ]
        for category in sorted(spent, key=lambda c: -spent[c]):
            candidate = self.candidates.get(category)
            state = ""
            if candidate is not None:
                state = (
                    f" [automated by {candidate.closed_by}]"
                    if candidate.closed_by
                    else " [automation candidate]"
                )
            lines.append(f"  {category}: {spent[category]}m{state}")
        return "\n".join(lines)
