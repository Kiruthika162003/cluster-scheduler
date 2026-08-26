"""Delivery arithmetic: four numbers describe a team's shipping health.

Lead time from commit to production, deploy frequency, change
failure rate, and time to restore: the four keys everyone cites
and few compute from their own ledger. This ledger computes them.
A deploy records when its commit landed and when it shipped; a
failure links back to the deploy that caused it and records when
service was restored. The rates come out of the ledger, not the
retro, which matters because memory undercounts failures by
whatever fraction was embarrassing. The trend method compares two
halves of a window so "we got slower" arrives with numbers while
it is still cheap to fix.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid, NotFound


@dataclass(frozen=True)
class Deploy:
    name: str
    committed: int
    shipped: int

    def __post_init__(self) -> None:
        if self.shipped < self.committed:
            raise Invalid("a deploy cannot ship before its commit")

    def lead_time(self) -> int:
        return self.shipped - self.committed


@dataclass
class DeliveryLedger:
    deploys: dict[str, Deploy] = field(default_factory=dict)
    failures: dict[str, tuple[int, int]] = field(default_factory=dict)

    def shipped(self, name: str, committed: int, shipped: int) -> None:
        if name in self.deploys:
            raise Invalid(f"{name} already shipped")
        self.deploys[name] = Deploy(
            name=name, committed=committed, shipped=shipped
        )

    def failed(self, deploy: str, noticed: int, restored: int) -> None:
        if deploy not in self.deploys:
            raise NotFound(f"no deploy named {deploy}")
        if restored <= noticed:
            raise Invalid("restoration must follow the failure")
        if deploy in self.failures:
            raise Invalid(f"{deploy} already has its failure on record")
        self.failures[deploy] = (noticed, restored)

    def lead_time_median(self) -> float:
        if not self.deploys:
            raise Invalid("nothing shipped yet")
        times = sorted(d.lead_time() for d in self.deploys.values())
        middle = len(times) // 2
        if len(times) % 2:
            return float(times[middle])
        return (times[middle - 1] + times[middle]) / 2

    def frequency(self, window: int) -> float:
        if window <= 0:
            raise Invalid("the window must be positive")
        return round(len(self.deploys) / window, 4)

    def failure_rate(self) -> float:
        if not self.deploys:
            raise Invalid("nothing shipped yet")
        return round(len(self.failures) / len(self.deploys), 4)

    def restore_time_mean(self) -> float:
        if not self.failures:
            raise Invalid("no failures on record")
        total = sum(
            restored - noticed
            for noticed, restored in self.failures.values()
        )
        return round(total / len(self.failures), 2)

    def trend(self, split_at: int) -> str:
        early = [
            d.lead_time()
            for d in self.deploys.values()
            if d.shipped < split_at
        ]
        late = [
            d.lead_time()
            for d in self.deploys.values()
            if d.shipped >= split_at
        ]
        if not early or not late:
            return "not enough history on one side of the split"
        early_mean = sum(early) / len(early)
        late_mean = sum(late) / len(late)
        if late_mean > early_mean * 1.25:
            return (
                f"slower: lead time {early_mean:.0f} -> {late_mean:.0f}; "
                f"say it now while it is cheap"
            )
        if late_mean < early_mean * 0.8:
            return f"faster: lead time {early_mean:.0f} -> {late_mean:.0f}"
        return "steady"

    def scorecard(self, window: int) -> str:
        lines = [
            f"lead time (median): {self.lead_time_median()}",
            f"deploys per tick: {self.frequency(window)}",
            f"change failure rate: {self.failure_rate():.0%}",
        ]
        if self.failures:
            lines.append(f"time to restore (mean): {self.restore_time_mean()}")
        return "\n".join(lines)
