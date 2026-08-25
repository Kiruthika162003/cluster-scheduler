"""Shifting the nightly batch out of the peak saves grams; the cap is the deadline.

A week of carbon windows: every evening ticks 18-22 cost 3.0 grams
per watt, every early morning 2-6 costs 0.2, and the flat day costs
1.0. Seven nightly 200-watt jobs arrive at their evening's tick 18
with a 12-tick deadline and a 4-tick span. The guess was the flat
shoulder past the peak, 1600 grams each, 11200 for the week. The
shifter did better: a 12-tick deadline reaches past midnight into
the NEXT morning's 0.2-gram trough, saving 2240 per job, except the
week's last job, which has no morning after it inside the calendar
and settles for the shoulder's 1600; the week saves 15040. Tightening the deadline to 4 ticks
removes every choice: the job runs inside the peak it arrived in and
the saving is exactly zero, which is the honest price of urgency.
"""

from __future__ import annotations

from fleet.energy import BatchShifter, CarbonCalendar, CarbonWindow
from fleet.trials.verdict import Verdict

DAYS = 7
DAY = 24


def _week_calendar() -> CarbonCalendar:
    calendar = CarbonCalendar()
    for day in range(DAYS):
        base = day * DAY
        calendar.add(
            CarbonWindow(starts=base + 18, ends=base + 22, grams_per_watt=3.0)
        )
        calendar.add(
            CarbonWindow(starts=base + 2, ends=base + 6, grams_per_watt=0.2)
        )
    return calendar


def _run_week(deadline_slack: int) -> float:
    shifter = BatchShifter(calendar=_week_calendar())
    saved = 0.0
    for day in range(DAYS):
        arrival = day * DAY + 18
        _, grams = shifter.place(
            f"etl-day{day}",
            watts=200,
            arrival=arrival,
            deadline=arrival + deadline_slack,
            span=4,
        )
        saved += grams
    return round(saved, 1)


def run() -> Verdict:
    numbers = {
        "saved_with_slack": _run_week(deadline_slack=12),
        "saved_when_urgent": _run_week(deadline_slack=4),
    }
    holds = (
        numbers["saved_with_slack"] == 15040.0
        and numbers["saved_when_urgent"] == 0.0
    )
    return Verdict(
        trial="greenshift",
        sentence=(
            "the shifter reaches into the next morning and saves 15040 for "
            "the week; a 4-tick deadline saves zero"
        ),
        numbers=numbers,
        holds=holds,
    )
