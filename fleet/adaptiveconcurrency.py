"""Adaptive concurrency: the limit finds the knee nobody can configure.

The right concurrency limit for a backend moves with every deploy
and every noisy neighbour, so a static number is wrong within a
week. The limiter probes for the knee of the latency curve with
AIMD: every round-trip that comes back under the latency target
adds a fraction of a slot, and a round-trip over the target cuts
the limit by a multiplicative factor, because congestion arrives
multiplicatively and must be answered in kind. Growth is additive
so the probe is gentle; the floor keeps one slot open so the
limiter can always learn the backend recovered. The history renders
as the classic sawtooth, climbing to the knee and backing off,
which is what a healthy limiter looks like and the flat line is
what a dead one looks like.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid

INCREASE = 0.5
BACKOFF = 0.6
FLOOR = 1.0


@dataclass
class AdaptiveLimit:
    latency_target: int
    limit: float = 4.0
    in_flight: int = 0
    history: list[float] = field(default_factory=list)
    refused: int = 0

    def __post_init__(self) -> None:
        if self.latency_target <= 0:
            raise Invalid("the latency target must be positive")

    def admit(self) -> bool:
        if self.in_flight < int(self.limit):
            self.in_flight += 1
            return True
        self.refused += 1
        return False

    def observe(self, latency: int) -> None:
        if self.in_flight <= 0:
            raise Invalid("an observation needs an admitted call")
        self.in_flight -= 1
        if latency <= self.latency_target:
            self.limit += INCREASE
        else:
            self.limit = max(FLOOR, self.limit * BACKOFF)
        self.history.append(round(self.limit, 2))

    def ceiling(self) -> int:
        return int(self.limit)

    def sawtooth(self) -> str:
        if not self.history:
            return "no observations"
        peak = max(self.history)
        trough = min(self.history)
        teeth = sum(
            1
            for before, after in zip(self.history, self.history[1:], strict=False)
            if after < before
        )
        return (
            f"limit swept {trough} to {peak} with {teeth} backoffs "
            f"({self.refused} refusals at the ceiling)"
        )
