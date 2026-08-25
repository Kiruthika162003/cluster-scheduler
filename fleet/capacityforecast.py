"""Capacity forecasting: time-to-full is the only date on this calendar.

A trend fitted to recent usage answers the question procurement
actually asks: at this growth, when does the fleet run out. The fit
is a least-squares line over the sample window, the answer is the
tick where the line crosses capacity, and the confidence is the
spread of the residuals, reported as a window rather than a point
because a forecast pretending to know the exact day is how teams
learn to ignore forecasts. Shrinking usage answers never, flat usage
answers not-on-this-trend, and both answers are real answers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass(frozen=True)
class Trend:
    slope: float
    intercept: float
    spread: float

    def value_at(self, tick: int) -> float:
        return self.slope * tick + self.intercept


def fit(samples: list[tuple[int, int]]) -> Trend:
    if len(samples) < 2:
        raise Invalid("a trend needs at least two samples")
    count = len(samples)
    mean_x = sum(tick for tick, _ in samples) / count
    mean_y = sum(used for _, used in samples) / count
    rise = sum(
        (tick - mean_x) * (used - mean_y) for tick, used in samples
    )
    run = sum((tick - mean_x) ** 2 for tick, used in samples)
    if run == 0:
        raise Invalid("all samples share one tick")
    slope = rise / run
    intercept = mean_y - slope * mean_x
    residuals = [
        abs(used - (slope * tick + intercept)) for tick, used in samples
    ]
    spread = max(residuals)
    return Trend(
        slope=round(slope, 4),
        intercept=round(intercept, 2),
        spread=round(spread, 2),
    )


@dataclass(frozen=True)
class Forecast:
    verdict: str
    full_at: int | None
    earliest: int | None
    latest: int | None

    def line(self) -> str:
        if self.verdict == "shrinking":
            return "usage is shrinking; on this trend the fleet never fills"
        if self.verdict == "flat":
            return "usage is flat; not full on this trend"
        return (
            f"full around tick {self.full_at} "
            f"(window {self.earliest} to {self.latest})"
        )


def time_to_full(trend: Trend, capacity: int, now: int) -> Forecast:
    if capacity <= 0:
        raise Invalid("capacity must be positive")
    if trend.slope < 0:
        return Forecast(
            verdict="shrinking", full_at=None, earliest=None, latest=None
        )
    if trend.slope == 0:
        return Forecast(verdict="flat", full_at=None, earliest=None, latest=None)
    crossing = (capacity - trend.intercept) / trend.slope
    early = (capacity - trend.spread - trend.intercept) / trend.slope
    late = (capacity + trend.spread - trend.intercept) / trend.slope
    return Forecast(
        verdict="filling",
        full_at=max(now, int(crossing)),
        earliest=max(now, int(early)),
        latest=max(now, int(late)),
    )


@dataclass
class UsageLog:
    window: int = 50
    samples: list[tuple[int, int]] = field(default_factory=list)

    def record(self, tick: int, used: int) -> None:
        self.samples.append((tick, used))
        horizon = tick - self.window
        self.samples = [
            (sample_tick, used_then)
            for sample_tick, used_then in self.samples
            if sample_tick > horizon
        ]

    def forecast(self, capacity: int, now: int) -> Forecast:
        return time_to_full(fit(self.samples), capacity, now)
