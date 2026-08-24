"""The warmup blind spot: a scaler that cannot see its pipeline overbuys.

Fourteen replicas land on two nodes that hold ten; four tasks stay
stuck. One new node would seat them all, but the naive scaler orders a
node every tick the stuckness persists, and stuckness persists exactly
as long as the warmup: five ticks of warmup buy six nodes for a one
node problem, five of which arrive empty, idle for the scale-down
window, and are retired having served nobody. The pipeline-aware scaler
orders once and waits. Both clear the backlog on the same tick; the
debt is everything after.
"""

from __future__ import annotations

from fleet.autoscale import NodeScaler
from fleet.control.deploy import DeploySpec
from fleet.objects import Resources, TaskSpec
from fleet.sim.cluster import Sim
from fleet.trials.verdict import Verdict


def _run(pipeline_aware: bool) -> Sim:
    sim = Sim(
        node_scaler=NodeScaler(
            warmup=5, scale_down_after=15, pipeline_aware=pipeline_aware
        )
    )
    sim.add_nodes(2)
    sim.deploys.append(
        DeploySpec(
            name="web",
            replicas=14,
            template=TaskSpec(name="tpl", needs=Resources(cpu=200, memory=200)),
        )
    )
    sim.run(60)
    return sim


def _cleared_at(sim: Sim) -> int:
    for tick, stuck in enumerate(sim.stuck_history):
        if stuck == 0:
            return tick
    return -1


def run() -> Verdict:
    naive = _run(pipeline_aware=False)
    aware = _run(pipeline_aware=True)

    numbers = {
        "nodes_ordered_naive": naive.node_scaler.provisioned,
        "nodes_ordered_aware": aware.node_scaler.provisioned,
        "cleared_at_naive": _cleared_at(naive),
        "cleared_at_aware": _cleared_at(aware),
        "idle_retired_naive": naive.node_scaler.retired,
        "idle_retired_aware": aware.node_scaler.retired,
    }
    holds = (
        naive.node_scaler.provisioned == 6
        and aware.node_scaler.provisioned == 1
        and _cleared_at(naive) == _cleared_at(aware) == 6
        and naive.node_scaler.retired == 5
        and aware.node_scaler.retired == 0
    )
    return Verdict(
        trial="warmupdebt",
        sentence=(
            "five ticks of warmup buy the naive scaler six nodes for a "
            "one node problem, and both scalers clear the backlog on tick "
            "6: the five extra nodes are pure debt, retired later having "
            "served nobody"
        ),
        numbers=numbers,
        holds=holds,
    )
