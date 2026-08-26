"""Graceful shutdown: the lame duck stops taking orders before it leaves.

Killing a serving process mid-request converts every in-flight
request into a user-visible error at the exact moment a deploy
wants to look boring. The choreography has three acts: lame duck,
where the process fails its readiness probe so balancers stop
sending work but keeps serving what it holds; drain, where
in-flight requests finish against a deadline; and the hard close,
where whatever outlives the deadline is cut and counted. The
deadline exists because one stuck request must not hold a deploy
hostage, and the count exists because "graceful" is a claim the
cut column can refute. The lame duck act must come first and last
long enough for every balancer to notice, since draining while new
work still arrives is bailing a boat that is still filling.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid

LAME_DUCK_TICKS = 5


@dataclass
class Shutdown:
    drain_deadline: int
    started_at: int | None = None
    in_flight: dict[str, int] = field(default_factory=dict)
    refused: int = 0
    finished: int = 0
    cut: list[str] = field(default_factory=list)
    phase: str = "serving"

    def __post_init__(self) -> None:
        if self.drain_deadline <= LAME_DUCK_TICKS:
            raise Invalid(
                "the deadline must outlast the lame duck act or the duck "
                "is theatre"
            )

    def accept(self, request: str, now: int, takes: int) -> bool:
        if self.phase != "serving":
            self.refused += 1
            return False
        self.in_flight[request] = now + takes
        return True

    def ready(self) -> bool:
        return self.phase == "serving"

    def begin(self, now: int) -> None:
        if self.phase != "serving":
            raise Invalid("shutdown already began")
        self.started_at = now
        self.phase = "lame-duck"

    def tick(self, now: int) -> str:
        if self.phase == "serving":
            self._finish_done(now)
            return "serving"
        elapsed = now - self.started_at
        if self.phase == "lame-duck" and elapsed >= LAME_DUCK_TICKS:
            self.phase = "draining"
        self._finish_done(now)
        if self.phase == "draining":
            if not self.in_flight:
                self.phase = "closed"
                return "closed clean"
            if elapsed >= self.drain_deadline:
                self.cut.extend(sorted(self.in_flight))
                self.in_flight.clear()
                self.phase = "closed"
                return f"closed hard: cut {len(self.cut)}"
        return self.phase

    def _finish_done(self, now: int) -> None:
        done = sorted(
            request
            for request, ends in self.in_flight.items()
            if ends <= now
        )
        for request in done:
            del self.in_flight[request]
            self.finished += 1

    def epitaph(self) -> str:
        graceful = "graceful" if not self.cut else "NOT graceful"
        return (
            f"{graceful}: {self.finished} finished, {self.refused} "
            f"refused during the duck, {len(self.cut)} cut at the deadline"
        )
