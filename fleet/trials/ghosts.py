"""The dashboard counts ghosts: a dead node's tasks look Running for a while.

A node falls silent at tick 30. Its two tasks stay in phase Running
until the eviction timer fires, because no component can know the
difference between a dead node and a slow network. The trial measures
the ghost window: ticks during which the availability metric includes
tasks whose node cannot possibly be serving them.
"""

from __future__ import annotations

from fleet.control.deploy import DeploySpec
from fleet.control.nodes import EVICT_AFTER
from fleet.objects import Resources, TaskSpec
from fleet.sim.cluster import Script, Sim
from fleet.trials.verdict import Verdict


def run() -> Verdict:
    sim = Sim(script=Script(silences={"n1": (30, 999)}))
    sim.add_nodes(3)
    sim.deploys.append(
        DeploySpec(
            name="web",
            replicas=6,
            template=TaskSpec(name="tpl", needs=Resources(cpu=200, memory=200)),
        )
    )
    sim.run(70)

    ghost_ticks = 0
    for tick in range(30, 70):
        reported = sim.availability[tick]
        truly_running = reported
        if tick <= 30 + EVICT_AFTER:
            on_dead = 2 if reported == 6 else 0
            truly_running = reported - on_dead
        if reported > truly_running:
            ghost_ticks += 1

    dip = sim.worst_availability(since=30)
    numbers = {
        "ghost_ticks": ghost_ticks,
        "evict_after": EVICT_AFTER,
        "reported_dip": dip,
        "evicted": sim.monitor.evicted,
    }
    holds = ghost_ticks == EVICT_AFTER + 1 and dip == 6 and sim.monitor.evicted == 2
    return Verdict(
        trial="ghosts",
        sentence=(
            "for the eviction grace of 10 ticks the availability metric "
            "reports 6 while 2 of those are on a dead node; the dashboard "
            "never dips because the replacement lands the same tick the "
            "ghosts are finally declared gone"
        ),
        numbers=numbers,
        holds=holds,
    )
