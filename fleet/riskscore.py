"""Change risk scoring: the approval chain should match the blast radius.

Every change form that asks the same questions for a comment fix
and a scheduler rewrite trains people to stop reading the form. The
score adds what actually predicts incidents: how much is changing,
how many deploys sit downstream of the target, whether the window
is hostile (Friday, night, freeze-adjacent), and whether this
deploy has burned anyone lately. Bands map to requirements a robot
can enforce: low rides the normal pipeline, medium adds a second
reviewer, high adds a canary and an owner's ack, and critical needs
the freeze glass treatment. The receipt itemises every point so an
engineer who disagrees argues with a line item instead of a
feeling.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.depends import DependencyGraph
from fleet.errors import Invalid

HOSTILE_HOURS = tuple(range(6))
FRIDAY = 4


@dataclass(frozen=True)
class Change:
    deploy: str
    lines_changed: int
    day_of_week: int
    hour: int
    recent_incidents: int

    def __post_init__(self) -> None:
        if self.lines_changed < 0 or self.recent_incidents < 0:
            raise Invalid("counts cannot be negative")
        if not 0 <= self.day_of_week <= 6 or not 0 <= self.hour <= 23:
            raise Invalid("the calendar has seven days and 24 hours")


@dataclass
class RiskScorer:
    graph: DependencyGraph
    items: list[tuple[str, int]] = field(default_factory=list)

    def _add(self, reason: str, points: int) -> None:
        if points:
            self.items.append((reason, points))

    def score(self, change: Change) -> int:
        self.items = []
        if change.lines_changed > 500:
            self._add(f"{change.lines_changed} lines changed", 3)
        elif change.lines_changed > 100:
            self._add(f"{change.lines_changed} lines changed", 2)
        elif change.lines_changed > 10:
            self._add(f"{change.lines_changed} lines changed", 1)
        downstream = len(self.graph.blast(change.deploy))
        if downstream >= 5:
            self._add(f"{downstream} deploys downstream", 3)
        elif downstream >= 2:
            self._add(f"{downstream} deploys downstream", 2)
        elif downstream == 1:
            self._add("1 deploy downstream", 1)
        if change.day_of_week == FRIDAY:
            self._add("shipping on a Friday", 2)
        if change.hour in HOSTILE_HOURS:
            self._add(f"shipping at {change.hour:02d}:00", 2)
        if change.recent_incidents:
            self._add(
                f"{change.recent_incidents} recent incident(s) here",
                2 * change.recent_incidents,
            )
        return sum(points for _, points in self.items)

    def band(self, change: Change) -> str:
        total = self.score(change)
        if total >= 8:
            return "critical"
        if total >= 5:
            return "high"
        if total >= 3:
            return "medium"
        return "low"

    def requirements(self, change: Change) -> list[str]:
        return {
            "low": ["normal pipeline"],
            "medium": ["normal pipeline", "second reviewer"],
            "high": ["canary first", "second reviewer", "owner ack"],
            "critical": [
                "canary first",
                "second reviewer",
                "owner ack",
                "break-glass approval with a name and a reason",
            ],
        }[self.band(change)]

    def receipt(self, change: Change) -> str:
        band = self.band(change)
        lines = [
            f"{change.deploy}: {band} "
            f"({sum(points for _, points in self.items)} points)"
        ]
        for reason, points in self.items:
            lines.append(f"  +{points} {reason}")
        for requirement in self.requirements(change):
            lines.append(f"  requires: {requirement}")
        return "\n".join(lines)
