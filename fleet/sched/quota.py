"""Dominant resource fairness: the fair share of a two-axis cluster.

Teams ask for tasks shaped differently: one is cpu-heavy, one is
memory-heavy. Splitting each axis evenly wastes whichever axis the team
does not want. DRF instead equalises each team's dominant share, the
largest fraction of any one axis it holds, and admits the next task for
whichever team currently holds the smallest dominant share. The result
is envy-free in shares while staying work-conserving in machines.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.objects import Resources


@dataclass
class Team:
    name: str
    shape: Resources
    admitted: int = 0

    def holding(self) -> Resources:
        return Resources(
            cpu=self.shape.cpu * self.admitted,
            memory=self.shape.memory * self.admitted,
        )


@dataclass
class Drf:
    capacity: Resources
    teams: list[Team] = field(default_factory=list)
    admissions: list[str] = field(default_factory=list)

    def dominant_share(self, team: Team) -> float:
        held = team.holding()
        return max(held.cpu / self.capacity.cpu, held.memory / self.capacity.memory)

    def _fits(self, team: Team) -> bool:
        used = Resources.none()
        for other in self.teams:
            used = used.plus(other.holding())
        after = used.plus(team.shape)
        return after.fits_in(self.capacity)

    def admit_next(self) -> str | None:
        """Admit one task for the poorest team that still fits; its name."""
        order = sorted(
            self.teams, key=lambda team: (self.dominant_share(team), team.name)
        )
        for team in order:
            if self._fits(team):
                team.admitted += 1
                self.admissions.append(team.name)
                return team.name
        return None

    def run_dry(self, limit: int = 10000) -> None:
        for _ in range(limit):
            if self.admit_next() is None:
                return
