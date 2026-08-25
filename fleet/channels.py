"""Release channels: the rapid cohort eats the bugs the stable cohort reads about.

A build promotes through channels, rapid first, stable after a soak.
Fleets subscribe to a channel, not a version, and the channel decides
when their version moves. The soak is the arrangement's entire value:
a build that breaks in rapid is yanked before stable ever sees it, and
the yank also freezes promotion until a fixed build arrives, because
promoting the next build on schedule after a yank is how the same bug
ships twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid

SOAK = 20


@dataclass
class Channels:
    rapid: str | None = None
    stable: str | None = None
    promoted_at: dict[str, int] = field(default_factory=dict)
    yanked: set[str] = field(default_factory=set)
    frozen: bool = False
    log: list[str] = field(default_factory=list)

    def release(self, build: str, now: int) -> None:
        if build in self.yanked:
            raise Invalid(f"{build} was yanked and cannot return")
        self.rapid = build
        self.promoted_at[build] = now
        self.log.append(f"[{now}] {build} to rapid")
        if self.frozen:
            self.frozen = False
            self.log.append(f"[{now}] promotion unfrozen by {build}")

    def yank(self, build: str, now: int) -> None:
        self.yanked.add(build)
        self.frozen = True
        if self.rapid == build:
            self.rapid = None
        if self.stable == build:
            self.stable = None
        self.log.append(f"[{now}] {build} yanked, promotion frozen")

    def tick(self, now: int) -> None:
        if self.frozen or self.rapid is None:
            return
        soaked_since = self.promoted_at.get(self.rapid)
        if soaked_since is None:
            return
        if now - soaked_since >= SOAK and self.stable != self.rapid:
            self.stable = self.rapid
            self.log.append(f"[{now}] {self.rapid} to stable after soak")

    def version_for(self, channel: str) -> str | None:
        if channel == "rapid":
            return self.rapid
        if channel == "stable":
            return self.stable
        raise Invalid(f"unknown channel {channel}")
