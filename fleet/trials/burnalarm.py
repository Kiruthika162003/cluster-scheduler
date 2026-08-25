"""The two-window alarm pages once for the real outage and never for noise.

A simulated day carries eight one-tick blips and one forty-tick real
outage at half availability. The guess was 79 fast-only alarm ticks
(five per blip); the measurement says 75, because the window's strict
inequality gives each one-tick blip exactly four alarm ticks and the
outage tail decays through 43. The dual-window alarm stays silent
through all eight blips and raises exactly one continuous alarm for
the outage, 12 ticks in, once the slow window crosses. Twelve ticks
of patience buys the on-call eight un-paged nights, and that trade
is the entire design.
"""

from __future__ import annotations

import itertools

from fleet.slo import BurnMeter, SloSpec
from fleet.trials.verdict import Verdict

BLIPS = (100, 200, 300, 400, 500, 600, 700, 800)
OUTAGE_START = 900
OUTAGE_TICKS = 40


def _day(meter: BurnMeter) -> tuple[int, int, int]:
    fast_only_pages = 0
    dual_alarm_ticks = []
    for tick in range(1000):
        if tick in BLIPS:
            good = 0
        elif OUTAGE_START <= tick < OUTAGE_START + OUTAGE_TICKS:
            good = 50
        else:
            good = 100
        meter.observe(tick, good=good, total=100)
        now = tick + 1
        if meter.fast_burn(now) >= meter.alarm_rate:
            fast_only_pages += 1
        if meter.alarming(now):
            dual_alarm_ticks.append(now)
    stretches = 1 if dual_alarm_ticks else 0
    for before, after in itertools.pairwise(dual_alarm_ticks):
        if after != before + 1:
            stretches += 1
    delay = (
        dual_alarm_ticks[0] - OUTAGE_START if dual_alarm_ticks else -1
    )
    return fast_only_pages, stretches, delay


def run() -> Verdict:
    meter = BurnMeter(
        spec=SloSpec(name="web", objective=0.99, window=2000)
    )
    fast_only_ticks, dual_stretches, delay = _day(meter)
    numbers = {
        "fast_only_alarm_ticks": fast_only_ticks,
        "dual_alarm_stretches": dual_stretches,
        "detection_delay": delay,
    }
    holds = (
        fast_only_ticks == 75
        and dual_stretches == 1
        and delay == 12
    )
    return Verdict(
        trial="burnalarm",
        sentence=(
            "fast-only would alarm for 75 ticks across the blips and the "
            "outage; the dual window raises one alarm, 12 ticks in"
        ),
        numbers=numbers,
        holds=holds,
    )
