"""Seasonal baselines: Tuesday 9am is only anomalous against Tuesday 9am.

Traffic has a pulse: mornings climb, nights rest, weekends differ
from weekdays. A single global threshold pages every Monday morning
and sleeps through a quiet-hour outage, because 60 percent of peak
is normal at 9am and catastrophic at 3am. The baseline keeps a
separate history per hour-of-week slot, judges each new reading
against its own slot's median and spread, and refuses to judge
slots it has not seen enough of, since a baseline with two samples
is a coin with opinions. Both failure directions matter: a spike
against the slot is a surge, a hole against the slot is the outage
the global threshold sleeps through, and the hole is the one this
detector exists for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.outliers import CONSISTENCY, mad, median

HOURS_PER_WEEK = 168
MINIMUM_HISTORY = 4
THRESHOLD = 3.5


@dataclass
class SeasonalBaseline:
    history: dict[int, list[float]] = field(default_factory=dict)
    keep: int = 8

    def slot_of(self, tick: int) -> int:
        return tick % HOURS_PER_WEEK

    def learn(self, tick: int, value: float) -> None:
        slot = self.history.setdefault(self.slot_of(tick), [])
        slot.append(value)
        del slot[: -self.keep]

    def judge(self, tick: int, value: float) -> str:
        slot = self.history.get(self.slot_of(tick), [])
        if len(slot) < MINIMUM_HISTORY:
            return "unjudgeable: not enough history for this slot"
        center = median(slot)
        spread = mad(slot) * CONSISTENCY
        if spread == 0:
            spread = max(abs(center) * 0.05, 0.5)
        score = (value - center) / spread
        if score >= THRESHOLD:
            return (
                f"surge: {value} against a slot median of {center} "
                f"(score {round(score, 1)})"
            )
        if score <= -THRESHOLD:
            return (
                f"hole: {value} against a slot median of {center} "
                f"(score {round(score, 1)})"
            )
        return "normal for this hour"

    def weeks_learned(self) -> int:
        if not self.history:
            return 0
        return min(len(slot) for slot in self.history.values())


def global_threshold_judge(
    value: float, peak: float, floor_share: float = 0.4
) -> str:
    """The single-threshold detector, kept for the comparison it loses."""
    if peak <= 0:
        raise Invalid("peak must be positive")
    if value < peak * floor_share:
        return "alert: below the global floor"
    return "fine by the global floor"
