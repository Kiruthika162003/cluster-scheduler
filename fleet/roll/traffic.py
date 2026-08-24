"""Traffic splitting with sticky sessions: the dial moves, the users do not.

A revision dial sends a share of new sessions to the canary build. But
sessions stick: a user who landed on the canary stays on it until their
session ends. The dial therefore controls arrivals, not population, and
the population lags the dial by the session length. The rollback case
is where the lag bites: the dial goes to zero and the bad build keeps
serving every user it already caught until their sessions drain.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Splitter:
    canary_share: float = 0.0
    session_length: int = 20
    sessions: dict[int, tuple[str, int]] = field(default_factory=dict)
    next_user: int = 0
    arrivals: dict[str, int] = field(default_factory=lambda: {"stable": 0, "canary": 0})

    def _assign(self, now: int) -> None:
        canary_due = round(self.canary_share * 10)
        lane = "canary" if (self.next_user % 10) < canary_due else "stable"
        self.sessions[self.next_user] = (lane, now + self.session_length)
        self.arrivals[lane] += 1
        self.next_user += 1

    def tick(self, now: int, new_users: int) -> None:
        for user, (_, ends) in list(self.sessions.items()):
            if ends <= now:
                del self.sessions[user]
        for _ in range(new_users):
            self._assign(now)

    def population(self) -> dict[str, int]:
        counts = {"stable": 0, "canary": 0}
        for lane, _ in self.sessions.values():
            counts[lane] += 1
        return counts

    def canary_population_share(self) -> float:
        counts = self.population()
        total = counts["stable"] + counts["canary"]
        return counts["canary"] / total if total else 0.0
