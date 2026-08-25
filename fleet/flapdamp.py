"""Flap dampening: the endpoint that cries wolf loses its audience for a while.

Every readiness flap adds penalty; penalty decays by half each
half-life; an endpoint whose penalty crosses the ceiling is suppressed
from rotation until decay brings it under the floor. The asymmetry is
the design: one flap is forgiven quickly, a burst of flaps buys a long
suppression, and a steady endpoint is never touched. Without decay the
suppression would be a life sentence for one bad afternoon, which is
how route dampening earned its bad reputation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PENALTY_PER_FLAP = 100.0
CEILING = 250.0
FLOOR = 80.0


@dataclass
class Dampener:
    half_life: int
    penalties: dict[str, float] = field(default_factory=dict)
    last_update: dict[str, int] = field(default_factory=dict)
    suppressed: set[str] = field(default_factory=set)
    suppressions: int = 0

    def _decayed(self, endpoint: str, now: int) -> float:
        penalty = self.penalties.get(endpoint, 0.0)
        since = now - self.last_update.get(endpoint, now)
        while since >= self.half_life:
            penalty /= 2
            since -= self.half_life
        return penalty

    def note_flap(self, endpoint: str, now: int) -> None:
        penalty = self._decayed(endpoint, now) + PENALTY_PER_FLAP
        self.penalties[endpoint] = penalty
        self.last_update[endpoint] = now
        if penalty >= CEILING and endpoint not in self.suppressed:
            self.suppressed.add(endpoint)
            self.suppressions += 1

    def in_rotation(self, endpoint: str, now: int) -> bool:
        penalty = self._decayed(endpoint, now)
        if endpoint in self.suppressed and penalty <= FLOOR:
            self.suppressed.discard(endpoint)
        return endpoint not in self.suppressed

    def penalty_of(self, endpoint: str, now: int) -> float:
        return self._decayed(endpoint, now)
