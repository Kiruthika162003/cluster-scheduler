"""Circuit breaking: stop asking a dead dependency to prove it is dead.

Every call to a failing dependency spends a timeout learning what
the last hundred calls already knew. The breaker counts failures in
a rolling window and opens at the threshold; open means calls fail
immediately with the breaker's name on the refusal, which converts
timeout seconds into microseconds and lets the dependency breathe.
After the cooldown the breaker goes half-open and admits a fixed
number of probes: all must succeed to close it, any failure reopens
with the cooldown restarted, because a dependency that answers one
probe and dies again was not back. The ledger counts what the open
state saved, in calls not spent waiting, since that number is the
breaker's entire salary.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid

FAILURE_THRESHOLD = 5
WINDOW = 20
COOLDOWN = 30
PROBES_TO_CLOSE = 3


@dataclass
class Breaker:
    name: str
    state: str = "closed"
    failures: list[int] = field(default_factory=list)
    opened_at: int | None = None
    probes_passed: int = 0
    shortcircuited: int = 0
    transitions: list[str] = field(default_factory=list)

    def _move(self, state: str, now: int, why: str) -> None:
        self.transitions.append(f"[{now}] {self.state} -> {state} ({why})")
        self.state = state

    def allow(self, now: int) -> tuple[bool, str]:
        if self.state == "open":
            if now - self.opened_at >= COOLDOWN:
                self.probes_passed = 0
                self._move("half-open", now, "cooldown elapsed")
                return True, "probe"
            self.shortcircuited += 1
            return False, f"breaker {self.name} is open"
        return True, "pass" if self.state == "closed" else "probe"

    def succeeded(self, now: int) -> None:
        if self.state == "half-open":
            self.probes_passed += 1
            if self.probes_passed >= PROBES_TO_CLOSE:
                self.failures.clear()
                self._move("closed", now, f"{self.probes_passed} probes passed")

    def failed(self, now: int) -> None:
        if self.state == "half-open":
            self.opened_at = now
            self._move("open", now, "a probe failed; it was not back")
            return
        if self.state != "closed":
            return
        self.failures.append(now)
        self.failures = [
            tick for tick in self.failures if now - tick < WINDOW
        ]
        if len(self.failures) >= FAILURE_THRESHOLD:
            self.opened_at = now
            self._move(
                "open",
                now,
                f"{len(self.failures)} failures inside {WINDOW} ticks",
            )

    def call(self, now: int, works: bool) -> str:
        allowed, why = self.allow(now)
        if not allowed:
            return f"refused: {why}"
        if works:
            self.succeeded(now)
            return "ok"
        self.failed(now)
        return "failed"

    def saved(self) -> int:
        return self.shortcircuited

    def story(self) -> str:
        lines = [f"{self.name}: {self.state}, saved {self.shortcircuited} waits"]
        lines.extend(f"  {line}" for line in self.transitions)
        return "\n".join(lines)


@dataclass
class BreakerBoard:
    breakers: dict[str, Breaker] = field(default_factory=dict)

    def watch(self, name: str) -> Breaker:
        if name in self.breakers:
            raise Invalid(f"{name} already has a breaker")
        breaker = Breaker(name=name)
        self.breakers[name] = breaker
        return breaker

    def open_now(self) -> list[str]:
        return sorted(
            name
            for name, breaker in self.breakers.items()
            if breaker.state == "open"
        )
