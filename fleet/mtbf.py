"""Failure arithmetic: availability is time remembered honestly.

MTBF and MTTR are averages of memories, and memories flatter: the
quarter had "a few blips" until the ledger shows 11 incidents
totalling 40 hours. The ledger records failures and repairs as
intervals, computes mean time between failures from actual gaps
and mean time to repair from actual outages, and turns the pair
into availability. The nines table converts that fraction into
allowed downtime, because "99.9 percent" sounds like a compliment
until it reads as 43 minutes a month. Overlapping outages on one
subject are refused at write time: a thing cannot break twice
before being fixed once, and a ledger that allows it will average
its way into fiction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass(frozen=True)
class Outage:
    started: int
    repaired: int

    def __post_init__(self) -> None:
        if self.repaired <= self.started:
            raise Invalid("a repair must come after its failure")

    def duration(self) -> int:
        return self.repaired - self.started


@dataclass
class FailureLedger:
    subject: str
    observed_from: int = 0
    outages: list[Outage] = field(default_factory=list)

    def record(self, started: int, repaired: int) -> None:
        candidate = Outage(started=started, repaired=repaired)
        for outage in self.outages:
            if (
                candidate.started < outage.repaired
                and outage.started < candidate.repaired
            ):
                raise Invalid(
                    f"{self.subject} cannot break twice before being "
                    f"fixed once"
                )
        self.outages.append(candidate)
        self.outages.sort(key=lambda outage: outage.started)

    def mttr(self) -> float:
        if not self.outages:
            raise Invalid("no outages recorded; nothing to average")
        total = sum(outage.duration() for outage in self.outages)
        return round(total / len(self.outages), 2)

    def mtbf(self) -> float:
        if len(self.outages) < 2:
            raise Invalid("mean time between failures needs two failures")
        gaps = [
            after.started - before.repaired
            for before, after in zip(
                self.outages, self.outages[1:], strict=False
            )
        ]
        return round(sum(gaps) / len(gaps), 2)

    def availability(self, until: int) -> float:
        window = until - self.observed_from
        if window <= 0:
            raise Invalid("the observation window is empty")
        down = sum(
            min(outage.repaired, until) - outage.started
            for outage in self.outages
            if outage.started < until
        )
        return round(1.0 - down / window, 6)

    def statement(self, until: int) -> str:
        count = len(self.outages)
        share = self.availability(until)
        line = f"{self.subject}: {count} outages, {share:.4%} available"
        if count >= 2:
            line += f", mtbf {self.mtbf()}, mttr {self.mttr()}"
        return line


def allowed_downtime(nines: float, window: int) -> int:
    """Ticks of downtime a given availability permits in a window."""
    if not 0.0 < nines < 1.0:
        raise Invalid("availability is a fraction strictly between 0 and 1")
    return int(window * (1.0 - nines))
