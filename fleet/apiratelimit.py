"""API rate limiting: the control plane survives its clients' enthusiasm.

One token bucket per client, refilled by the tick, with a shared
reserve behind them: a client that exhausts its own bucket may draw
from the reserve only while the reserve is above its floor, so a
burst is absorbed but a flood is not. Refused calls carry a
retry-after computed from the refill rate rather than a guess,
because a client told "try again in 3" behaves and a client told
"no" retries immediately and makes everything worse. A starvation
guard watches for clients refused many rounds in a row while the
fleet's total intake stayed under the global rate; that pattern
means the buckets are mis-sized, not the clients misbehaved, and
the guard says so instead of letting the small client take the
blame.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass
class Bucket:
    rate: float
    burst: int
    level: float = 0.0
    filled_at: int = 0

    def __post_init__(self) -> None:
        if self.rate <= 0 or self.burst <= 0:
            raise Invalid("rate and burst must be positive")
        self.level = float(self.burst)

    def refill(self, now: int) -> None:
        elapsed = now - self.filled_at
        if elapsed > 0:
            self.level = min(float(self.burst), self.level + elapsed * self.rate)
            self.filled_at = now

    def take(self, now: int) -> bool:
        self.refill(now)
        if self.level >= 1.0:
            self.level -= 1.0
            return True
        return False

    def wait_for_one(self, now: int) -> int:
        self.refill(now)
        if self.level >= 1.0:
            return 0
        deficit = 1.0 - self.level
        ticks = deficit / self.rate
        return int(ticks) + (0 if ticks == int(ticks) else 1)


@dataclass
class Limiter:
    reserve: Bucket
    reserve_floor: float = 2.0
    clients: dict[str, Bucket] = field(default_factory=dict)
    refused_streak: dict[str, int] = field(default_factory=dict)
    accepted: int = 0
    refused: int = 0

    def register(self, client: str, rate: float, burst: int) -> None:
        if client in self.clients:
            raise Invalid(f"{client} is already registered")
        self.clients[client] = Bucket(rate=rate, burst=burst)

    def allow(self, client: str, now: int) -> tuple[bool, int]:
        """Returns (allowed, retry_after)."""
        if client not in self.clients:
            raise Invalid(f"{client} is not registered")
        bucket = self.clients[client]
        if bucket.take(now):
            self.accepted += 1
            self.refused_streak[client] = 0
            return True, 0
        self.reserve.refill(now)
        if self.reserve.level - 1.0 >= self.reserve_floor:
            self.reserve.level -= 1.0
            self.accepted += 1
            self.refused_streak[client] = 0
            return True, 0
        self.refused += 1
        self.refused_streak[client] = self.refused_streak.get(client, 0) + 1
        return False, bucket.wait_for_one(now)

    def starving(self, threshold: int = 5) -> list[str]:
        return sorted(
            client
            for client, streak in self.refused_streak.items()
            if streak >= threshold
        )

    def diagnosis(self, threshold: int = 5) -> str:
        starved = self.starving(threshold)
        if not starved:
            return "no starvation"
        total = self.accepted + self.refused
        refusal_share = self.refused / total if total else 0.0
        if refusal_share < 0.2:
            return (
                f"{', '.join(starved)} starving while global refusals are "
                f"{refusal_share:.0%}: the buckets are mis-sized, "
                f"not the clients misbehaved"
            )
        return (
            f"{', '.join(starved)} starving under real pressure "
            f"({refusal_share:.0%} refused overall)"
        )
