"""Waves: the same build walks dev, staging, prod, and a failure stops the walk.

A delivery is a sequence of environments, each with a bake time: the
build must sit healthy for the whole bake before the next wave starts.
A failure anywhere aborts the walk and nothing downstream ever sees the
build. The point of the structure is measured elsewhere as the canary's
lesson at fleet scale: evidence accumulates environment by environment,
and prod's exposure to a bad build is zero when any earlier wave does
its job.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Wave:
    environment: str
    bake: int


@dataclass
class Delivery:
    build: str
    waves: tuple[Wave, ...]
    at: int = 0
    baked: int = 0
    state: str = "rolling"
    log: list[str] = field(default_factory=list)

    def current(self) -> Wave | None:
        if self.at >= len(self.waves):
            return None
        return self.waves[self.at]

    def tick(self, healthy: bool) -> str:
        if self.state != "rolling":
            return self.state
        wave = self.current()
        if wave is None:
            self.state = "delivered"
            return self.state
        if not healthy:
            self.state = "aborted"
            self.log.append(f"{wave.environment}: unhealthy, walk aborted")
            return self.state
        self.baked += 1
        if self.baked >= wave.bake:
            self.log.append(f"{wave.environment}: baked {wave.bake}, promoted")
            self.at += 1
            self.baked = 0
            if self.at >= len(self.waves):
                self.state = "delivered"
        return self.state

    def reached(self) -> list[str]:
        return [wave.environment for wave in self.waves[: self.at]] + (
            [self.current().environment] if self.current() else []
        )


def standard() -> tuple[Wave, ...]:
    return (
        Wave(environment="dev", bake=5),
        Wave(environment="staging", bake=10),
        Wave(environment="prod", bake=20),
    )
