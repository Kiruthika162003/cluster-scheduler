"""SLOs: the error budget is the only permission slip that matters.

An objective like "99 percent of requests succeed over 30 days" turns
into a budget of allowed failures; the budget turns into a burn rate;
the burn rate turns into decisions. Two windows watch the burn: a
fast one that catches a cliff within minutes and a slow one that
catches a leak within hours. A page fires only when both agree,
which is the classic trick for pages that are neither late nor
jumpy: the fast window alone flaps on noise, the slow window alone
sleeps through the first hour of an outage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass(frozen=True)
class SloSpec:
    name: str
    objective: float
    window: int

    def __post_init__(self):
        if not 0.0 < self.objective < 1.0:
            raise Invalid(f"objective must be a fraction, got {self.objective}")
        if self.window <= 0:
            raise Invalid("window must be positive")

    @property
    def budget_fraction(self) -> float:
        return 1.0 - self.objective


@dataclass
class Sample:
    tick: int
    good: int
    total: int


@dataclass
class BurnMeter:
    spec: SloSpec
    fast_window: int = 5
    slow_window: int = 60
    alarm_rate: float = 10.0
    samples: list[Sample] = field(default_factory=list)

    def observe(self, tick: int, good: int, total: int) -> None:
        if good > total:
            raise Invalid(f"good {good} exceeds total {total}")
        self.samples.append(Sample(tick=tick, good=good, total=total))
        horizon = tick - self.spec.window
        while self.samples and self.samples[0].tick <= horizon:
            self.samples.pop(0)

    def _rate_over(self, now: int, span: int) -> float:
        good = total = 0
        for sample in self.samples:
            if now - sample.tick < span:
                good += sample.good
                total += sample.total
        if total == 0:
            return 0.0
        failing = (total - good) / total
        return failing / self.spec.budget_fraction

    def fast_burn(self, now: int) -> float:
        return round(self._rate_over(now, self.fast_window), 2)

    def slow_burn(self, now: int) -> float:
        return round(self._rate_over(now, self.slow_window), 2)

    def alarming(self, now: int) -> bool:
        return (
            self.fast_burn(now) >= self.alarm_rate
            and self.slow_burn(now) >= self.alarm_rate
        )

    def budget_left(self) -> float:
        good = sum(sample.good for sample in self.samples)
        total = sum(sample.total for sample in self.samples)
        if total == 0:
            return 1.0
        allowed = total * self.spec.budget_fraction
        spent = total - good
        return round(max(0.0, (allowed - spent) / allowed), 4) if allowed else 0.0

    def exhausted(self) -> bool:
        return self.budget_left() <= 0.0

    def line(self, now: int) -> str:
        return (
            f"{self.spec.name}: budget {self.budget_left():.1%} left, "
            f"burning {self.fast_burn(now)}x fast / {self.slow_burn(now)}x slow"
            + (" [ALARM]" if self.alarming(now) else "")
        )


@dataclass
class SloBoard:
    meters: dict[str, BurnMeter] = field(default_factory=dict)

    def watch(self, spec: SloSpec, **knobs) -> BurnMeter:
        meter = BurnMeter(spec=spec, **knobs)
        self.meters[spec.name] = meter
        return meter

    def observe(self, name: str, tick: int, good: int, total: int) -> None:
        if name not in self.meters:
            raise Invalid(f"no meter watches {name}")
        self.meters[name].observe(tick, good, total)

    def alarms(self, now: int) -> list[str]:
        return sorted(
            name
            for name, meter in self.meters.items()
            if meter.alarming(now)
        )

    def frozen_deploys(self) -> list[str]:
        """Deploys whose budget is gone stop shipping; that is the deal."""
        return sorted(
            name
            for name, meter in self.meters.items()
            if meter.exhausted()
        )

    def report(self, now: int) -> str:
        lines = [f"{len(self.meters)} objectives, {len(self.alarms(now))} alarming"]
        for name in sorted(self.meters):
            lines.append("  " + self.meters[name].line(now))
        return "\n".join(lines)
