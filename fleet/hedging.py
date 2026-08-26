"""Request hedging: buy the tail with a second request, and price the buy.

The slowest percentile of requests dominates user pain, and most of
that tail is one unlucky server, not a hard request. A hedged call
sends the primary, waits the hedge delay, and if no answer has come
sends one backup to a different replica; first answer wins, the
loser is cancelled. The delay is the whole design: hedge at p95 and
only the slowest 5 percent of calls pay a second request, but that
5 percent is exactly the tail being bought. The meter reports both
sides of the trade, tail latency bought and extra load paid,
because hedging every call at delay zero is a doubling of traffic
wearing a latency costume.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass(frozen=True)
class HedgedCall:
    primary_latency: int
    backup_latency: int | None
    hedged: bool
    winner: str
    delivered: int


@dataclass
class Hedger:
    hedge_delay: int
    calls: list[HedgedCall] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.hedge_delay < 0:
            raise Invalid("the hedge delay cannot be negative")

    def call(self, primary_latency: int, backup_latency: int) -> HedgedCall:
        if primary_latency <= self.hedge_delay:
            outcome = HedgedCall(
                primary_latency=primary_latency,
                backup_latency=None,
                hedged=False,
                winner="primary",
                delivered=primary_latency,
            )
        else:
            backup_finish = self.hedge_delay + backup_latency
            if backup_finish < primary_latency:
                outcome = HedgedCall(
                    primary_latency=primary_latency,
                    backup_latency=backup_latency,
                    hedged=True,
                    winner="backup",
                    delivered=backup_finish,
                )
            else:
                outcome = HedgedCall(
                    primary_latency=primary_latency,
                    backup_latency=backup_latency,
                    hedged=True,
                    winner="primary",
                    delivered=primary_latency,
                )
        self.calls.append(outcome)
        return outcome

    def extra_load(self) -> float:
        if not self.calls:
            return 0.0
        hedged = sum(1 for call in self.calls if call.hedged)
        return round(hedged / len(self.calls), 3)

    def delivered_latencies(self) -> list[int]:
        return sorted(call.delivered for call in self.calls)

    def unhedged_latencies(self) -> list[int]:
        return sorted(call.primary_latency for call in self.calls)

    def percentile(self, values: list[int], fraction: float) -> int:
        if not values:
            raise Invalid("no calls yet")
        index = int(fraction * (len(values) - 1) + 0.5)
        return values[index]

    def trade(self) -> str:
        with_hedge = self.percentile(self.delivered_latencies(), 0.99)
        without = self.percentile(self.unhedged_latencies(), 0.99)
        return (
            f"p99 {without} -> {with_hedge} for "
            f"{self.extra_load():.1%} extra load"
        )
