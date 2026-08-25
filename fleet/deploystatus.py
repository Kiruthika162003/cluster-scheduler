"""Rollout status: the sentence behind the progress bar.

A rollout in flight has four populations: updated and available,
updated but not yet serving, old and still serving, old and going. The
status collapses them into the sentence an operator actually reads,
n of m updated, k available, and a stall detector that speaks up when
the numbers have not moved for a while, because a progress bar that
has quietly stopped is worse than no bar at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.roll.rolling import Roller, Rollout
from fleet.store import Store


@dataclass(frozen=True)
class Status:
    wanted: int
    updated: int
    updated_available: int
    old_serving: int

    def done(self) -> bool:
        return self.updated_available >= self.wanted and self.old_serving == 0

    def sentence(self) -> str:
        if self.done():
            return f"rollout complete: {self.updated_available} of {self.wanted} available"
        return (
            f"{self.updated} of {self.wanted} updated, "
            f"{self.updated_available} available, "
            f"{self.old_serving} old still serving"
        )


def status_of(store: Store, roller: Roller, roll: Rollout) -> Status:
    fresh = roller.fresh(store, roll)
    stale = roller.stale(store, roll)
    return Status(
        wanted=roll.replicas,
        updated=len(fresh),
        updated_available=sum(1 for task in fresh if task.phase == "Running"),
        old_serving=sum(1 for task in stale if task.phase == "Running"),
    )


@dataclass
class StallWatch:
    patience: int
    last_sentence: str = ""
    unchanged_for: int = 0
    stalls: list[str] = field(default_factory=list)

    def observe(self, status: Status, tick: int) -> str | None:
        sentence = status.sentence()
        if sentence == self.last_sentence and not status.done():
            self.unchanged_for += 1
        else:
            self.unchanged_for = 0
            self.last_sentence = sentence
        if self.unchanged_for == self.patience:
            stall = (
                f"[{tick}] rollout stalled {self.patience} ticks at: {sentence}"
            )
            self.stalls.append(stall)
            return stall
        return None
