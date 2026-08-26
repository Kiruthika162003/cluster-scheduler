"""Phi accrual failure detection: suspicion is a number, not a verdict.

A fixed heartbeat timeout is wrong twice: too short and every GC
pause is a funeral, too long and real deaths take a timeout to
notice. The phi detector learns each peer's own heartbeat rhythm,
mean and deviation over a sliding window, and reports suspicion as
a continuous number: how surprising is this silence, given how this
peer usually talks. A peer with steady heartbeats earns a tight
model whose phi climbs fast when it goes quiet; a jittery peer
earns a loose model that forgives its wobble. Callers choose their
own threshold per decision, low for stopping new placements, high
for the irreversible eviction, which is the entire point: one
detector, many verdicts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from fleet.errors import Invalid

WINDOW = 20
MINIMUM_SAMPLES = 3
FLOOR_DEVIATION = 0.5


@dataclass
class PeerRhythm:
    arrivals: list[int] = field(default_factory=list)
    intervals: list[int] = field(default_factory=list)

    def beat(self, now: int) -> None:
        if self.arrivals:
            gap = now - self.arrivals[-1]
            if gap < 0:
                raise Invalid("heartbeats cannot arrive in the past")
            self.intervals.append(gap)
            self.intervals = self.intervals[-WINDOW:]
        self.arrivals.append(now)
        self.arrivals = self.arrivals[-2:]

    def mean(self) -> float:
        return sum(self.intervals) / len(self.intervals)

    def deviation(self) -> float:
        mean = self.mean()
        variance = sum(
            (value - mean) ** 2 for value in self.intervals
        ) / len(self.intervals)
        return max(FLOOR_DEVIATION, math.sqrt(variance))

    def phi(self, now: int) -> float:
        if len(self.intervals) < MINIMUM_SAMPLES:
            return 0.0
        silence = now - self.arrivals[-1]
        if silence <= 0:
            return 0.0
        z = (silence - self.mean()) / self.deviation()
        if z <= 0:
            return 0.0
        tail = 0.5 * math.erfc(z / math.sqrt(2))
        if tail <= 0:
            return 40.0
        return round(min(40.0, -math.log10(tail)), 3)


@dataclass
class PhiDetector:
    peers: dict[str, PeerRhythm] = field(default_factory=dict)

    def heartbeat(self, peer: str, now: int) -> None:
        self.peers.setdefault(peer, PeerRhythm()).beat(now)

    def suspicion(self, peer: str, now: int) -> float:
        if peer not in self.peers:
            raise Invalid(f"{peer} has never spoken")
        return self.peers[peer].phi(now)

    def suspects(self, now: int, threshold: float) -> list[str]:
        return sorted(
            peer
            for peer, rhythm in self.peers.items()
            if rhythm.phi(now) >= threshold
        )

    def report(self, now: int) -> str:
        lines = []
        for peer in sorted(self.peers):
            phi = self.peers[peer].phi(now)
            lines.append(f"{peer}: phi {phi}")
        return "\n".join(lines) if lines else "no peers"
