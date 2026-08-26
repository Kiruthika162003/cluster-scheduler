"""Shard autosplit: hot shards divide, cold shards merge, moves are priced.

A static shard layout is wrong within a season: one tenant grows
tenfold and their shard becomes the fleet's heartbeat problem. The
splitter watches per-shard load, splits any shard sustaining more
than double the fleet mean at its key-range midpoint, and merges
adjacent shards whose combined load sits under half the mean,
because a thousand starving shards cost metadata and heartbeats
even when they cost no cpu. Both operations carry hysteresis: a
shard must hold its state for the dwell period before acting, so a
spike splits nothing and a lull merges nothing. Every action is
priced in moved keys before it runs, and the planner refuses any
action whose price exceeds its budget, which keeps the layout from
thrashing its way to optimality through a cache-flush storm.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid

SPLIT_FACTOR = 2.0
MERGE_FACTOR = 0.5
DWELL = 5


@dataclass
class Shard:
    low: int
    high: int
    load: int = 0
    hot_since: int | None = None
    cold_since: int | None = None

    def width(self) -> int:
        return self.high - self.low

    def name(self) -> str:
        return f"[{self.low},{self.high})"


@dataclass
class Splitter:
    shards: list[Shard]
    move_budget: int
    actions: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.shards:
            raise Invalid("a layout needs at least one shard")

    def observe(self, loads: dict[int, int], now: int) -> list[str]:
        for shard in self.shards:
            shard.load = loads.get(shard.low, 0)
        mean = sum(shard.load for shard in self.shards) / len(self.shards)
        acted = []
        acted.extend(self._mark_and_split(mean, now))
        acted.extend(self._mark_and_merge(mean, now))
        return acted

    def _mark_and_split(self, mean: float, now: int) -> list[str]:
        acted = []
        for shard in list(self.shards):
            if shard.load > SPLIT_FACTOR * mean and shard.width() > 1:
                if shard.hot_since is None:
                    shard.hot_since = now
                    continue
                if now - shard.hot_since < DWELL:
                    continue
                acted.extend(self._split(shard))
            else:
                shard.hot_since = None
        return acted

    def _split(self, shard: Shard) -> list[str]:
        price = shard.load // 2
        if price > self.move_budget:
            line = (
                f"refused split of {shard.name()}: moving {price} keys "
                f"exceeds budget {self.move_budget}"
            )
            self.refused.append(line)
            return []
        middle = (shard.low + shard.high) // 2
        index = self.shards.index(shard)
        left = Shard(low=shard.low, high=middle, load=shard.load // 2)
        right = Shard(low=middle, high=shard.high, load=shard.load // 2)
        self.shards[index : index + 1] = [left, right]
        line = f"split {shard.name()} at {middle}, moved {price} keys"
        self.actions.append(line)
        return [line]

    def _mark_and_merge(self, mean: float, now: int) -> list[str]:
        acted = []
        index = 0
        while index < len(self.shards) - 1:
            left = self.shards[index]
            right = self.shards[index + 1]
            combined = left.load + right.load
            if combined < MERGE_FACTOR * mean:
                if left.cold_since is None:
                    left.cold_since = now
                    index += 1
                    continue
                if now - left.cold_since < DWELL:
                    index += 1
                    continue
                price = min(left.load, right.load)
                if price > self.move_budget:
                    self.refused.append(
                        f"refused merge at {left.name()}: {price} keys "
                        f"over budget"
                    )
                    index += 1
                    continue
                merged = Shard(
                    low=left.low, high=right.high, load=combined
                )
                self.shards[index : index + 2] = [merged]
                line = (
                    f"merged {left.name()} and {right.name()}, "
                    f"moved {price} keys"
                )
                self.actions.append(line)
                acted.append(line)
            else:
                left.cold_since = None
                index += 1
        return acted

    def layout(self) -> str:
        return " ".join(
            f"{shard.name()}={shard.load}" for shard in self.shards
        )
