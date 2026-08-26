"""Golden signals: four numbers per deploy, and the fifth is a diagnosis.

Latency, traffic, errors, saturation: the four questions that catch
almost everything, asked together because each one alone misleads.
Rising latency with flat traffic is the service degrading; rising
latency with doubled traffic is the service succeeding at a bigger
job and needing help. The board keeps a short window per deploy,
answers with current value and direction for each signal, and the
diagnosis line combines them into the sentence an operator would
have derived by squinting: degrading, growing into its limits,
erroring under load, or healthy. The combination table is small and
explicit, because a diagnosis nobody can audit is astrology with
graphs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid

WINDOW = 10
RISING = 1.2
SATURATED = 0.8
ERRORING = 0.02


@dataclass
class SignalWindow:
    values: list[float] = field(default_factory=list)

    def push(self, value: float) -> None:
        self.values.append(value)
        self.values = self.values[-WINDOW:]

    def current(self) -> float:
        if not self.values:
            raise Invalid("no samples")
        return self.values[-1]

    def direction(self) -> str:
        if len(self.values) < 4:
            return "flat"
        half = len(self.values) // 2
        early = sum(self.values[:half]) / half
        late = sum(self.values[half:]) / (len(self.values) - half)
        if early == 0:
            return "rising" if late > 0 else "flat"
        ratio = late / early
        if ratio >= RISING:
            return "rising"
        if ratio <= 1 / RISING:
            return "falling"
        return "flat"


@dataclass
class DeploySignals:
    latency: SignalWindow = field(default_factory=SignalWindow)
    traffic: SignalWindow = field(default_factory=SignalWindow)
    errors: SignalWindow = field(default_factory=SignalWindow)
    saturation: SignalWindow = field(default_factory=SignalWindow)

    def observe(
        self,
        latency: float,
        traffic: float,
        errors: float,
        saturation: float,
    ) -> None:
        if not 0.0 <= saturation <= 1.0:
            raise Invalid("saturation is a fraction")
        self.latency.push(latency)
        self.traffic.push(traffic)
        self.errors.push(errors)
        self.saturation.push(saturation)

    def diagnosis(self) -> str:
        slow = self.latency.direction() == "rising"
        busier = self.traffic.direction() == "rising"
        erroring = self.errors.current() >= ERRORING
        saturated = self.saturation.current() >= SATURATED
        if erroring and saturated:
            return "erroring under load: shed or scale, in that order"
        if erroring:
            return "erroring without pressure: this is a bug, not capacity"
        if slow and busier:
            return "growing into its limits: add capacity before the knee"
        if slow and not busier:
            return "degrading: same work, worse answers; look at the deploy"
        if saturated:
            return "hot but holding: watch the next window"
        return "healthy"


@dataclass
class SignalBoard:
    deploys: dict[str, DeploySignals] = field(default_factory=dict)

    def observe(self, deploy: str, **signals: float) -> None:
        self.deploys.setdefault(deploy, DeploySignals()).observe(**signals)

    def unhealthy(self) -> list[tuple[str, str]]:
        rows = []
        for deploy in sorted(self.deploys):
            verdict = self.deploys[deploy].diagnosis()
            if verdict != "healthy":
                rows.append((deploy, verdict))
        return rows

    def page(self) -> str:
        rows = self.unhealthy()
        if not rows:
            return f"{len(self.deploys)} deploys, all healthy"
        lines = [f"{len(rows)} of {len(self.deploys)} deploys need eyes"]
        for deploy, verdict in rows:
            lines.append(f"  {deploy}: {verdict}")
        return "\n".join(lines)
