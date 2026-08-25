"""Auto-pause on stall: the rollout stops digging and calls for hands.

The stall watch already notices a frozen rollout; the autopauser acts
on it, pausing the roller so no further step compounds whatever went
wrong, and paging once with the stalled sentence. Resume is a human
verb on purpose: an automation that pauses on evidence and resumes on
a timer has merely invented a slower way to continue digging.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.deploystatus import StallWatch, status_of
from fleet.roll.rolling import Roller, Rollout
from fleet.store import Store


@dataclass
class AutoPauser:
    watch: StallWatch
    pages: list[str] = field(default_factory=list)
    paused_rollouts: list[str] = field(default_factory=list)

    def observe(
        self, store: Store, roller: Roller, roll: Rollout, tick: int
    ) -> str | None:
        told = status_of(store, roller, roll)
        stall = self.watch.observe(told, tick)
        if stall is None:
            return None
        roller.pause()
        self.paused_rollouts.append(roll.name)
        page = f"{stall}; rollout paused, resume is yours"
        self.pages.append(page)
        return page
