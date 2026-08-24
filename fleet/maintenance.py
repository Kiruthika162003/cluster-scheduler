"""Freeze windows: the calendar is a controller too.

Changes hurt most when nobody is watching. A freeze window names the
ticks during which voluntary change, rollouts and drains, must wait;
involuntary work, evictions from dead nodes and reschedules, never
waits for a calendar. The gate answers with the next open tick so a
refused change can sleep precisely instead of polling.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Window:
    start: int
    end: int
    reason: str

    def covers(self, tick: int) -> bool:
        return self.start <= tick < self.end


@dataclass
class Calendar:
    windows: list[Window] = field(default_factory=list)
    refusals: int = 0

    def add(self, window: Window) -> None:
        self.windows.append(window)
        self.windows.sort(key=lambda held: held.start)

    def frozen_at(self, tick: int) -> Window | None:
        for window in self.windows:
            if window.covers(tick):
                return window
        return None

    def may_change(self, tick: int) -> tuple[bool, int]:
        """(allowed, next open tick). Walks chained windows to the first gap."""
        window = self.frozen_at(tick)
        if window is None:
            return True, tick
        self.refusals += 1
        opens = window.end
        walk = self.frozen_at(opens)
        while walk is not None:
            opens = walk.end
            walk = self.frozen_at(opens)
        return False, opens


@dataclass
class GatedRoller:
    """A rollout step that consults the calendar before doing anything."""

    calendar: Calendar
    waited: int = 0

    def step(self, roller, store, roll, tick: int) -> str:
        allowed, opens = self.calendar.may_change(tick)
        if not allowed:
            self.waited += 1
            return f"frozen-until-{opens}"
        return roller.step(store, roll)
