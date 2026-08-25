"""Alert routing: the pager and the catalog composed into one dispatcher.

The pager knows how to dedup and damp; the catalog knows who owns
what. Neither alone can answer "who hears about this, and who hears
about it next when nobody acks". The router joins them: a firing
alert about a deploy passes through the pager's filters first, and
only events the pager believes become dispatches, resolved through
the catalog to a channel and an escalation ladder. Unacked pages
climb the ladder on a fixed cadence, alerts about deploys nobody
registered land on a fallback channel instead of vanishing, and the
escalation clock starts at the first dispatch, not the first firing,
so a deduped flap does not silently pre-age its own escalation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.alerts import Event, Pager
from fleet.catalog import Catalog
from fleet.errors import NotFound

ESCALATE_AFTER = 15


@dataclass
class Dispatch:
    alert: str
    deploy: str
    channel: str
    person: str
    rung: int
    at: int


@dataclass
class Router:
    catalog: Catalog
    pager: Pager = field(default_factory=Pager)
    fallback_channel: str = "#unowned-alerts"
    dispatches: list[Dispatch] = field(default_factory=list)
    paged_at: dict[str, int] = field(default_factory=dict)
    rung: dict[str, int] = field(default_factory=dict)
    acked: set[str] = field(default_factory=set)

    def fire(self, alert: str, deploy: str, now: int) -> Dispatch | None:
        key = f"{alert}/{deploy}"
        heard = len(self.pager.pages)
        self.pager.take(Event(tick=now, subject=key, state="firing"))
        if len(self.pager.pages) == heard:
            return None
        if key in self.paged_at and key not in self.acked:
            return None
        self.paged_at[key] = now
        self.rung[key] = 0
        self.acked.discard(key)
        return self._dispatch(alert, deploy, 0, now)

    def ack(self, alert: str, deploy: str) -> None:
        self.acked.add(f"{alert}/{deploy}")

    def resolve(self, alert: str, deploy: str, now: int) -> None:
        key = f"{alert}/{deploy}"
        self.pager.take(Event(tick=now, subject=key, state="resolved"))
        self.paged_at.pop(key, None)
        self.rung.pop(key, None)
        self.acked.discard(key)

    def tick(self, now: int) -> list[Dispatch]:
        climbed = []
        for key, first in sorted(self.paged_at.items()):
            if key in self.acked:
                continue
            alert, deploy = key.split("/", 1)
            due = first + (self.rung[key] + 1) * ESCALATE_AFTER
            if now < due:
                continue
            if self.rung[key] + 1 >= self._ladder_length(deploy):
                continue
            self.rung[key] += 1
            climbed.append(self._dispatch(alert, deploy, self.rung[key], now))
        return climbed

    def _ladder_length(self, deploy: str) -> int:
        try:
            return len(self.catalog.owner_of(deploy).escalation)
        except NotFound:
            return 1

    def _dispatch(self, alert: str, deploy: str, rung: int, now: int) -> Dispatch:
        try:
            entry = self.catalog.owner_of(deploy)
            dispatch = Dispatch(
                alert=alert,
                deploy=deploy,
                channel=entry.channel,
                person=self.catalog.page_target(deploy, rung),
                rung=rung,
                at=now,
            )
        except NotFound:
            dispatch = Dispatch(
                alert=alert,
                deploy=deploy,
                channel=self.fallback_channel,
                person="whoever-is-watching",
                rung=rung,
                at=now,
            )
        self.dispatches.append(dispatch)
        return dispatch

    def unheard(self) -> list[str]:
        return sorted(key for key in self.paged_at if key not in self.acked)

    def report(self) -> str:
        lines = [
            f"{len(self.dispatches)} dispatches, {len(self.unheard())} unheard"
        ]
        for dispatch in self.dispatches:
            lines.append(
                f"  [{dispatch.at:>4}] {dispatch.alert} on {dispatch.deploy} "
                f"-> {dispatch.person} in {dispatch.channel} "
                f"(rung {dispatch.rung})"
            )
        return "\n".join(lines)
