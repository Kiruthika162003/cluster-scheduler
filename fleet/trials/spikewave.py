"""A traffic spike against the replica scaler: undersupply, itemised.

Demand runs at 300 for thirty ticks, steps to 1500 for thirty, and
falls back. Capacity is replicas times each replica's hundred-unit
ceiling; every tick demand exceeds capacity drops the excess. Both
scalers eat the first tick's 1000-unit surprise, because no reactive
scaler can act before the tick it reacts to. The difference is the
tail: the step-limited scaler climbs four replicas a tick and drops
another 800 while climbing, 1800 in all; the unlimited one jumps to
its ceiling and is done at 1000. The stability the step limit bought
in the scaler fight is billed here, in dropped requests during honest
spikes, which is the two trials agreeing the knob is a trade.
"""

from __future__ import annotations

from fleet.autoscale import ReplicaScaler
from fleet.trials.verdict import Verdict

CEILING = 100


def _demand(tick: int) -> float:
    return 1500.0 if 30 <= tick < 60 else 300.0


def _ride(step_limit: int) -> tuple[int, int]:
    scaler = ReplicaScaler(floor=3, ceiling=20, step_limit=step_limit)
    replicas = 3
    dropped = 0
    worst_tick = 0
    for tick in range(90):
        demand = _demand(tick)
        capacity = replicas * CEILING
        if demand > capacity:
            dropped += int(demand - capacity)
            worst_tick = max(worst_tick, int(demand - capacity))
        replicas = scaler.wanted(replicas, demand)
    return dropped, worst_tick


def run() -> Verdict:
    damped_dropped, damped_worst = _ride(step_limit=4)
    eager_dropped, eager_worst = _ride(step_limit=100)

    numbers = {
        "dropped_damped": damped_dropped,
        "worst_tick_damped": damped_worst,
        "dropped_eager": eager_dropped,
        "worst_tick_eager": eager_worst,
    }
    holds = (
        damped_dropped == 1800
        and eager_dropped == 1000
        and damped_worst == eager_worst == 1000
    )
    return Verdict(
        trial="spikewave",
        sentence=(
            "both scalers eat the first tick's 1000 because reaction "
            "starts a tick late; the step limit then drops another 800 "
            "while climbing where the unlimited jump is already done: "
            "the stability bought in the scaler fight is billed here in "
            "dropped requests"
        ),
        numbers=numbers,
        holds=holds,
    )
