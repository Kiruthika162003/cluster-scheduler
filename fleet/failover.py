"""Active passive failover: the knob does not remove the poison, it picks one.

Two sites run one service. The watcher sees reachability, not truth: a
partitioned active is alive, still serving its side, and cannot be told
to demote until the partition heals. Promote after too few failed
checks and a blip yields two actives, split brain; wait too long and a
real death yields zero, outage. The pair of meters across the same
partition shows the whole trade: every setting of the knob buys ticks
of one failure with ticks of the other.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Site:
    name: str
    up: bool = True
    reachable: bool = True
    role: str = "passive"

    def serving(self) -> bool:
        return self.up and self.role == "active"


@dataclass
class Watcher:
    promote_after: int
    consecutive_failures: int = 0
    promotions: int = 0

    def observe(self, active: Site, passive: Site) -> None:
        if active.up and active.reachable:
            self.consecutive_failures = 0
            return
        self.consecutive_failures += 1
        may_promote = (
            self.consecutive_failures >= self.promote_after
            and passive.up
            and passive.role != "active"
        )
        if may_promote:
            passive.role = "active"
            if active.reachable:
                active.role = "passive"
            self.promotions += 1
            self.consecutive_failures = 0


@dataclass
class Pair:
    east: Site
    west: Site
    watcher: Watcher
    split_brain_ticks: int = 0
    outage_ticks: int = 0
    history: list[str] = field(default_factory=list)

    def _demote_returners(self) -> None:
        if self.east.role == self.west.role == "active":
            for site in (self.east, self.west):
                if site.reachable and site.name == "east":
                    site.role = "passive"

    def tick(self, east_up: bool, east_reachable: bool, west_up: bool = True) -> None:
        self.east.up = east_up
        self.east.reachable = east_reachable
        self.west.up = west_up
        self._demote_returners()
        active = self.east if self.east.role == "active" else self.west
        passive = self.west if active is self.east else self.east
        self.watcher.observe(active, passive)
        actives_serving = sum(
            1 for site in (self.east, self.west) if site.serving()
        )
        if actives_serving > 1:
            self.split_brain_ticks += 1
        if actives_serving == 0:
            self.outage_ticks += 1
        self.history.append(
            "+".join(
                site.name for site in (self.east, self.west) if site.serving()
            )
            or "nobody"
        )


def partition_story(promote_after: int) -> Pair:
    """East is partitioned for six ticks but alive, then heals; later it dies."""
    pair = Pair(
        east=Site(name="east", role="active"),
        west=Site(name="west"),
        watcher=Watcher(promote_after=promote_after),
    )
    for now in range(30):
        if 2 <= now < 8:
            pair.tick(east_up=True, east_reachable=False)
        elif 15 <= now < 25:
            pair.tick(east_up=False, east_reachable=False)
        else:
            pair.tick(east_up=True, east_reachable=True)
    return pair
