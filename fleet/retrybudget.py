"""Retry budgets: retries are borrowed capacity, and outages call the loan.

When a service dips, naive clients retry everything and triple the
load on whatever survived, which is how a blip becomes an outage.
The budget caps retries as a fraction of recent successful traffic:
healthy traffic earns retry credit, an outage stops earning it, and
the retry storm dies of bankruptcy instead of killing the backend.
First attempts are never budgeted, only retries, so the cap cannot
lock out fresh work. The meter reports the amplification factor,
total sends over first attempts, because that ratio is the number
the backend experiences: 1.0 is a polite client, 3.0 is a siege
tower, and the budget holds it near the configured ceiling through
the worst tick of the outage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid

WINDOW = 20


@dataclass
class RetryBudget:
    ratio: float = 0.1
    successes: list[int] = field(default_factory=list)
    retries_spent: list[int] = field(default_factory=list)
    first_attempts: int = 0
    total_sends: int = 0
    denied: int = 0

    def __post_init__(self) -> None:
        if not 0.0 <= self.ratio <= 1.0:
            raise Invalid("the retry ratio is a fraction of traffic")

    def _trim(self, now: int) -> None:
        self.successes = [t for t in self.successes if now - t < WINDOW]
        self.retries_spent = [
            t for t in self.retries_spent if now - t < WINDOW
        ]

    def send(self) -> None:
        self.first_attempts += 1
        self.total_sends += 1

    def succeeded(self, now: int) -> None:
        self._trim(now)
        self.successes.append(now)

    def may_retry(self, now: int) -> bool:
        self._trim(now)
        allowance = int(len(self.successes) * self.ratio)
        if len(self.retries_spent) < allowance:
            self.retries_spent.append(now)
            self.total_sends += 1
            return True
        self.denied += 1
        return False

    def amplification(self) -> float:
        if self.first_attempts == 0:
            return 1.0
        return round(self.total_sends / self.first_attempts, 3)

    def statement(self) -> str:
        return (
            f"amplification {self.amplification()}, "
            f"{len(self.retries_spent)} retries in flight, "
            f"{self.denied} denied"
        )
