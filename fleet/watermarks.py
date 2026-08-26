"""Watermarks: the stream admits what it does not know yet.

Events arrive late and out of order, and any aggregate closed at
wall-clock time silently drops the stragglers. The watermark trails
the maximum event time seen by a fixed lateness allowance and only
advances, never retreats; a window closes when the watermark passes
its end, which converts "probably complete" into a definition. Late
events, behind the watermark on arrival, are counted and routed by
policy: dropped, or applied as a correction to the closed window
with the correction flagged, because silently editing a closed
total is how two dashboards end up in a meeting arguing. The
lateness histogram is the tuning tool: it shows what allowance
would have caught which share of the stragglers, so the allowance
is chosen from data instead of vibes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass
class Window:
    start: int
    end: int
    total: int = 0
    events: int = 0
    closed: bool = False
    corrections: int = 0


@dataclass
class WatermarkStream:
    window_size: int
    allowance: int
    late_policy: str = "correct"
    watermark: int = -1
    top_event_time: int = -1
    windows: dict[int, Window] = field(default_factory=dict)
    late_seen: list[int] = field(default_factory=list)
    dropped: int = 0

    def __post_init__(self) -> None:
        if self.window_size <= 0 or self.allowance < 0:
            raise Invalid("window size must be positive, allowance nonnegative")
        if self.late_policy not in ("drop", "correct"):
            raise Invalid(f"unknown late policy {self.late_policy}")

    def _window_for(self, event_time: int) -> Window:
        start = (event_time // self.window_size) * self.window_size
        if start not in self.windows:
            self.windows[start] = Window(
                start=start, end=start + self.window_size
            )
        return self.windows[start]

    def accept(self, event_time: int, value: int) -> str:
        if event_time < 0:
            raise Invalid("event time cannot be negative")
        late_by = self.watermark - event_time
        if late_by > 0:
            self.late_seen.append(late_by)
            if self.late_policy == "drop":
                self.dropped += 1
                return f"dropped: {late_by} behind the watermark"
            window = self._window_for(event_time)
            window.total += value
            window.events += 1
            if window.closed:
                window.corrections += 1
                return f"corrected a closed window ({late_by} late)"
            return f"late but the window was still open ({late_by})"
        self.top_event_time = max(self.top_event_time, event_time)
        moved = max(self.watermark, self.top_event_time - self.allowance)
        self.watermark = moved
        window = self._window_for(event_time)
        window.total += value
        window.events += 1
        self._close_passed()
        return "on time"

    def _close_passed(self) -> None:
        for window in self.windows.values():
            if not window.closed and self.watermark >= window.end:
                window.closed = True

    def closed_totals(self) -> dict[int, int]:
        return {
            start: window.total
            for start, window in sorted(self.windows.items())
            if window.closed
        }

    def allowance_that_catches(self, share: float) -> int:
        """What allowance would have admitted this share of stragglers."""
        if not 0.0 < share <= 1.0:
            raise Invalid("share is a fraction over zero")
        if not self.late_seen:
            return self.allowance
        ordered = sorted(self.late_seen)
        index = min(len(ordered) - 1, int(share * len(ordered) + 0.5) - 1)
        return self.allowance + ordered[max(0, index)]

    def report(self) -> str:
        closed = self.closed_totals()
        corrected = sum(
            1 for window in self.windows.values() if window.corrections
        )
        return (
            f"watermark {self.watermark}, {len(closed)} windows closed, "
            f"{len(self.late_seen)} stragglers "
            f"({self.dropped} dropped, {corrected} windows corrected)"
        )
