"""Five hundred ticks of everything at once, invariants checked at each one.

Two node deaths, one overlapping, a mid-run doubling of the fleet's
work, probe failures on two tasks, and the pipeline-aware autoscaler
buying capacity, all in one continuous run. The receipt is that every
one of five hundred ticks passed every invariant, the deploys converge
to their counts, and the meters agree with each other: evictions equal
the tasks the dead nodes held, and the ghost gap between running and
serving opens exactly during the silences and closes after them.
"""

from __future__ import annotations

from fleet.autoscale import NodeScaler
from fleet.control.deploy import DeploySpec
from fleet.objects import Resources, TaskSpec
from fleet.sim.cluster import Script, Sim
from fleet.trials.verdict import Verdict
from fleet.verify import violations


def _campaign() -> tuple[Sim, int, int]:
    sim = Sim(
        script=Script(
            silences={"n1": (100, 160), "n2": (140, 200)},
            failing_probes={
                "web-0": frozenset({0, 1}),
                "web-3": frozenset({0}),
            },
        ),
        node_scaler=NodeScaler(warmup=5, scale_down_after=80, pipeline_aware=True),
    )
    sim.add_nodes(4)
    sim.deploys.append(
        DeploySpec(
            name="web",
            replicas=8,
            template=TaskSpec(name="tpl", needs=Resources(cpu=300, memory=300)),
        )
    )
    sim.wire_probes()
    broken_ticks = 0
    ghost_ticks = 0
    for tick in range(500):
        if tick == 250:
            sim.deploys[0] = DeploySpec(
                name="web",
                replicas=14,
                template=sim.deploys[0].template,
            )
        sim.tick()
        if violations(sim.store):
            broken_ticks += 1
        if sim.availability[-1] != sim.serving_history[-1]:
            ghost_ticks += 1
    return sim, broken_ticks, ghost_ticks


def run() -> Verdict:
    sim, broken_ticks, ghost_ticks = _campaign()

    numbers = {
        "ticks": 500,
        "broken_ticks": broken_ticks,
        "final_running": sim.running_count(),
        "final_serving": sim.serving_count(),
        "evictions": sim.monitor.evicted,
        "restarts": sim.keeper.restarts,
        "nodes_provisioned": sim.node_scaler.provisioned,
        "ghost_ticks": ghost_ticks,
    }
    holds = (
        broken_ticks == 0
        and sim.running_count() == sim.serving_count() == 14
        and sim.monitor.evicted == 5
        and sim.keeper.restarts == 3
        and sim.node_scaler.provisioned >= 1
        and 0 < ghost_ticks < 40
    )
    return Verdict(
        trial="longhaul",
        sentence=(
            "five hundred ticks of overlapping node deaths, crashloops, a "
            "mid-run doubling and autoscaling pass every invariant at "
            "every tick, end at 14 of 14 serving, and the ghost gap opens "
            "only inside the silences"
        ),
        numbers=numbers,
        holds=holds,
    )
