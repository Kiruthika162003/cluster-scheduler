"""An incident, tick by tick: a node dies on launch morning.

Run with: python -m examples.incident
"""

from __future__ import annotations

from fleet.autoscale import NodeScaler
from fleet.control.deploy import DeploySpec
from fleet.objects import Resources, TaskSpec
from fleet.sim.cluster import Script, Sim


def main() -> int:
    sim = Sim(
        script=Script(silences={"n1": (25, 999)}),
        node_scaler=NodeScaler(warmup=5, scale_down_after=30, pipeline_aware=True),
    )
    sim.add_nodes(3)
    sim.deploys.append(
        DeploySpec(
            name="web",
            replicas=12,
            template=TaskSpec(name="tpl", needs=Resources(cpu=240, memory=240)),
        )
    )
    sim.run(80)

    print(f"replicas wanted 12, running at the end {sim.running_count()}")
    print(f"n1 fell silent at 25; evictions {sim.monitor.evicted}")
    print(
        "stuck tasks per tick around the failure:",
        sim.stuck_history[34:44],
    )
    print(f"autoscaler provisioned {sim.node_scaler.provisioned} replacement node(s)")
    print(f"nodes at the end: {sorted(sim.store.nodes)}")
    worst = sim.worst_availability(since=25)
    print(f"worst running count after the failure: {worst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
