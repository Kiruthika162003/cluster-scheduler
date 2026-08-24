"""Canary analysis: promote on evidence, roll back on evidence, never on hope.

A canary takes a small share of traffic and reports errors alongside the
stable fleet. The judge compares rates over a window and rules promote,
rollback, or keep watching. The subtlety is sample size: a canary at one
percent of traffic needs a long window before its error rate means
anything, and the judge refuses to rule before the canary has seen
enough requests to tell signal from luck.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MINIMUM_REQUESTS = 200


@dataclass
class Ledger:
    requests: int = 0
    errors: int = 0

    def note(self, requests: int, errors: int) -> None:
        self.requests += requests
        self.errors += errors

    def rate(self) -> float:
        return self.errors / self.requests if self.requests else 0.0


@dataclass
class Judge:
    tolerance: float = 2.0
    rulings: list[str] = field(default_factory=list)

    def rule(self, stable: Ledger, canary: Ledger) -> str:
        if canary.requests < MINIMUM_REQUESTS:
            ruling = "watch"
        elif stable.rate() == 0.0:
            ruling = "rollback" if canary.rate() > 0.0 else "promote"
        elif canary.rate() > stable.rate() * self.tolerance:
            ruling = "rollback"
        else:
            ruling = "promote"
        self.rulings.append(ruling)
        return ruling


@dataclass
class Canary:
    traffic_share: float
    judge: Judge = field(default_factory=Judge)
    stable: Ledger = field(default_factory=Ledger)
    canary: Ledger = field(default_factory=Ledger)
    state: str = "watching"

    def tick(
        self, total_requests: int, stable_error_rate: float, canary_error_rate: float
    ) -> str:
        if self.state != "watching":
            return self.state
        canary_requests = int(total_requests * self.traffic_share)
        stable_requests = total_requests - canary_requests
        self.stable.note(
            stable_requests, round(stable_requests * stable_error_rate)
        )
        self.canary.note(
            canary_requests, round(canary_requests * canary_error_rate)
        )
        ruling = self.judge.rule(self.stable, self.canary)
        if ruling in ("promote", "rollback"):
            self.state = ruling
        return self.state
