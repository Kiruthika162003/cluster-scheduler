"""Blackbox probing: the service is up when a stranger says it is.

Internal health is testimony from the accused; the prober asks from
outside. Each round sends one synthetic request per target through
the balancer path and records latency or a named failure. The
verdict per target needs consecutive evidence in both directions,
up after UP_AFTER clean rounds and down after DOWN_AFTER failed
ones, so a single dropped packet does not flip a dashboard. The
history keeps the last transitions with their evidence, because "it
went down at 4:12 after three timeouts" is the sentence the incident
review actually needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid

UP_AFTER = 2
DOWN_AFTER = 3


@dataclass(frozen=True)
class ProbeResult:
    tick: int
    target: str
    latency: int | None
    failure: str | None

    def ok(self) -> bool:
        return self.failure is None


@dataclass
class TargetState:
    verdict: str = "unknown"
    streak_ok: int = 0
    streak_bad: int = 0
    results: list[ProbeResult] = field(default_factory=list)
    transitions: list[str] = field(default_factory=list)

    def take(self, result: ProbeResult) -> str | None:
        self.results.append(result)
        if result.ok():
            self.streak_ok += 1
            self.streak_bad = 0
        else:
            self.streak_bad += 1
            self.streak_ok = 0
        if self.verdict != "up" and self.streak_ok >= UP_AFTER:
            return self._flip("up", result.tick, f"{self.streak_ok} clean rounds")
        if self.verdict != "down" and self.streak_bad >= DOWN_AFTER:
            evidence = ", ".join(
                r.failure for r in self.results[-DOWN_AFTER:] if r.failure
            )
            return self._flip("down", result.tick, evidence)
        return None

    def _flip(self, verdict: str, tick: int, evidence: str) -> str:
        self.verdict = verdict
        line = f"[{tick}] -> {verdict} ({evidence})"
        self.transitions.append(line)
        return line

    def latencies(self) -> list[int]:
        return sorted(
            r.latency for r in self.results if r.latency is not None
        )


@dataclass
class Prober:
    targets: dict[str, TargetState] = field(default_factory=dict)

    def watch(self, target: str) -> None:
        if target in self.targets:
            raise Invalid(f"{target} is already watched")
        self.targets[target] = TargetState()

    def observe(
        self,
        target: str,
        tick: int,
        latency: int | None = None,
        failure: str | None = None,
    ) -> str | None:
        if target not in self.targets:
            raise Invalid(f"{target} is not watched")
        if (latency is None) == (failure is None):
            raise Invalid("exactly one of latency or failure")
        return self.targets[target].take(
            ProbeResult(
                tick=tick, target=target, latency=latency, failure=failure
            )
        )

    def down(self) -> list[str]:
        return sorted(
            name
            for name, state in self.targets.items()
            if state.verdict == "down"
        )

    def report(self) -> str:
        lines = [f"{len(self.targets)} targets, {len(self.down())} down"]
        for name in sorted(self.targets):
            state = self.targets[name]
            speeds = state.latencies()
            middle = speeds[len(speeds) // 2] if speeds else "-"
            lines.append(
                f"  {name}: {state.verdict}, median {middle}, "
                f"{len(state.transitions)} transitions"
            )
            for transition in state.transitions[-2:]:
                lines.append(f"    {transition}")
        return "\n".join(lines)
