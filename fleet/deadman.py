"""The deadman switch: who watches the controllers, and what silence means.

Every controller checks in each pass; the deadman pages when a
registered controller misses its allowance. The subtlety is the boot
grace: a controller that has never checked in is starting, not dead,
and paging on it teaches everyone to ignore the first page of every
deploy. Silence after a first heartbeat is the real signal, and the
page names the controller and the length of the silence, because the
on-call's first question is always which one and how long.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Deadman:
    allowance: int
    registered: dict[str, int | None] = field(default_factory=dict)
    pages: list[str] = field(default_factory=list)
    paged: set[str] = field(default_factory=set)

    def register(self, controller: str) -> None:
        self.registered.setdefault(controller, None)

    def beat(self, controller: str, now: int) -> None:
        if controller not in self.registered:
            self.register(controller)
        self.registered[controller] = now
        self.paged.discard(controller)

    def sweep(self, now: int) -> list[str]:
        fresh = []
        for controller, last in sorted(self.registered.items()):
            if last is None:
                continue
            silence = now - last
            if silence > self.allowance and controller not in self.paged:
                page = (
                    f"[{now}] {controller} silent {silence}, "
                    f"allowance {self.allowance}"
                )
                self.pages.append(page)
                self.paged.add(controller)
                fresh.append(page)
        return fresh

    def standing(self, now: int) -> list[str]:
        return [
            f"{controller}: never checked in"
            if last is None
            else f"{controller}: {now - last} ago"
            for controller, last in sorted(self.registered.items())
        ]
