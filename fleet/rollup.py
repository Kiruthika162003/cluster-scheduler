"""Metric rollups: resolution is spent where the questions are recent.

Raw samples answer "what happened at 14:03"; nobody asks that about
last quarter. The ladder keeps raw points for a short span, then
folds them into coarser rungs, each fold keeping min, max, and mean
rather than mean alone, because the spike that pages is precisely
the point a mean-only rollup erases. Queries route to the finest
rung that still covers the asked range, and the store's size is
bounded by construction: every rung has a fixed capacity and folds
feed the next rung instead of growing this one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass(frozen=True)
class Point:
    tick: int
    low: float
    high: float
    mean: float
    weight: int

    @classmethod
    def raw(cls, tick: int, value: float) -> Point:
        return cls(tick=tick, low=value, high=value, mean=value, weight=1)


def fold(points: list[Point], tick: int) -> Point:
    if not points:
        raise Invalid("cannot fold nothing")
    weight = sum(point.weight for point in points)
    mean = sum(point.mean * point.weight for point in points) / weight
    return Point(
        tick=tick,
        low=min(point.low for point in points),
        high=max(point.high for point in points),
        mean=round(mean, 4),
        weight=weight,
    )


@dataclass
class Rung:
    span: int
    capacity: int
    points: list[Point] = field(default_factory=list)

    def covers_back_to(self, now: int) -> int:
        return now - self.capacity * self.span


@dataclass
class Ladder:
    rungs: list[Rung] = field(
        default_factory=lambda: [
            Rung(span=1, capacity=60),
            Rung(span=10, capacity=60),
            Rung(span=100, capacity=60),
        ]
    )
    folded_away: int = 0

    def record(self, tick: int, value: float) -> None:
        self._push(0, Point.raw(tick, value))

    def _push(self, index: int, point: Point) -> None:
        rung = self.rungs[index]
        rung.points.append(point)
        if len(rung.points) <= rung.capacity:
            return
        batch_size = (
            self.rungs[index + 1].span // rung.span
            if index + 1 < len(self.rungs)
            else None
        )
        if batch_size is None:
            dropped = rung.points.pop(0)
            self.folded_away += dropped.weight
            return
        if len(rung.points) >= rung.capacity + batch_size:
            batch = rung.points[:batch_size]
            del rung.points[:batch_size]
            self._push(index + 1, fold(batch, batch[-1].tick))

    def query(self, since: int, now: int) -> list[Point]:
        """The finest rung whose window still reaches back to `since`."""
        for rung in self.rungs:
            if rung.covers_back_to(now) <= since and rung.points:
                return [
                    point for point in rung.points if point.tick >= since
                ]
        coarsest = self.rungs[-1]
        return [point for point in coarsest.points if point.tick >= since]

    def spike_survives(self, threshold: float) -> bool:
        """The reason min and max ride along on every fold."""
        return any(
            point.high >= threshold
            for rung in self.rungs
            for point in rung.points
        )

    def footprint(self) -> int:
        return sum(len(rung.points) for rung in self.rungs)
