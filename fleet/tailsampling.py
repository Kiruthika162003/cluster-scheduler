"""Tail sampling: keep every interesting trace, admit what the rest cost.

Storing every trace is a mortgage; sampling uniformly throws away
the slow and broken ones, which are the only traces anyone opens.
Tail sampling decides after the trace completes: errors are always
kept, latencies over the slow line are always kept, and the boring
majority is kept one-in-N. The counts that come out of a sampled
store are estimates, so every kept boring trace carries its weight
of N and the estimator multiplies honestly; the interesting traces
carry weight one because they were never sampled. The blindness
report says what the store cannot answer, the exact count of any
boring subcategory, because a sampling pipeline that will not name
its blind spots gets trusted for answers it does not have.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass(frozen=True)
class Trace:
    name: str
    latency: int
    failed: bool


@dataclass(frozen=True)
class Kept:
    trace: Trace
    weight: int
    reason: str


@dataclass
class TailSampler:
    slow_line: int
    keep_one_in: int
    kept: list[Kept] = field(default_factory=list)
    seen: int = 0
    boring_seen: int = 0

    def __post_init__(self) -> None:
        if self.keep_one_in <= 0 or self.slow_line <= 0:
            raise Invalid("the sampler needs positive knobs")

    def offer(self, trace: Trace) -> str:
        self.seen += 1
        if trace.failed:
            self.kept.append(Kept(trace=trace, weight=1, reason="error"))
            return "kept: error"
        if trace.latency >= self.slow_line:
            self.kept.append(Kept(trace=trace, weight=1, reason="slow"))
            return "kept: slow"
        self.boring_seen += 1
        if self.boring_seen % self.keep_one_in == 0:
            self.kept.append(
                Kept(trace=trace, weight=self.keep_one_in, reason="sampled")
            )
            return f"kept: 1 in {self.keep_one_in}"
        return "dropped"

    def stored(self) -> int:
        return len(self.kept)

    def estimated_total(self) -> int:
        return sum(entry.weight for entry in self.kept)

    def exact_interesting(self) -> int:
        return sum(1 for entry in self.kept if entry.weight == 1)

    def estimate_error(self) -> float:
        if self.seen == 0:
            raise Invalid("nothing offered yet")
        drift = abs(self.estimated_total() - self.seen)
        return round(drift / self.seen, 4)

    def blindness(self) -> str:
        return (
            f"exact answers exist for errors and slow traces "
            f"({self.exact_interesting()} kept at weight 1); any count "
            f"inside the boring {self.boring_seen} is an estimate with "
            f"steps of {self.keep_one_in}"
        )

    def statement(self) -> str:
        share = self.stored() / self.seen if self.seen else 0.0
        return (
            f"{self.stored()} stored of {self.seen} seen ({share:.1%}), "
            f"estimated total {self.estimated_total()} "
            f"(error {self.estimate_error():.2%})"
        )
