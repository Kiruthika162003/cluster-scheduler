"""Shadow traffic: the canary watches errors, the shadow watches answers.

A candidate build can serve every request without failing one and
still be wrong: the discount that rounds the other way, the sort that
ties differently. The shadow mirrors real requests to the candidate,
compares its responses against production's, and counts disagreements
by kind. Error-rate canaries are blind to this whole class because a
wrong answer with a 200 on it is a success as far as they know; the
shadow diff is the only meter pointed at correctness itself.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class ShadowDiff:
    compared: int = 0
    agreed: int = 0
    disagreements: dict[str, int] = field(default_factory=dict)
    samples: list[str] = field(default_factory=list)
    sample_cap: int = 5

    def mirror(
        self,
        request: object,
        production: Callable[[object], object],
        candidate: Callable[[object], object],
    ) -> object:
        truth = production(request)
        shadow = candidate(request)
        self.compared += 1
        if truth == shadow:
            self.agreed += 1
        else:
            kind = type(request).__name__
            self.disagreements[kind] = self.disagreements.get(kind, 0) + 1
            if len(self.samples) < self.sample_cap:
                self.samples.append(
                    f"request {request!r}: production {truth!r}, "
                    f"candidate {shadow!r}"
                )
        return truth

    def agreement_rate(self) -> float:
        if not self.compared:
            return 1.0
        return self.agreed / self.compared

    def verdict(self, floor: float = 0.999) -> str:
        rate = self.agreement_rate()
        if rate >= floor:
            return f"promote: {rate:.2%} agreement over {self.compared}"
        return (
            f"hold: {rate:.2%} agreement, "
            f"{self.compared - self.agreed} disagreements"
        )
