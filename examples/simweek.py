"""A week on call: seven days of the fleet, one page of what happened.

Run with: python -m examples.simweek
"""

from __future__ import annotations

from fleet.autoscale import NodeScaler
from fleet.control.deploy import DeploySpec
from fleet.drift import Detector
from fleet.metrics import scrape
from fleet.objects import Resources, TaskSpec
from fleet.sim.cluster import Script, Sim
from fleet.verify import violations

DAY = 20


def main() -> int:
    sim = Sim(
        script=Script(silences={"n2": (2 * DAY + 5, 2 * DAY + 18)}),
        node_scaler=NodeScaler(warmup=5, scale_down_after=25, pipeline_aware=True),
    )
    sim.add_nodes(4)
    web = DeploySpec(
        name="web",
        replicas=8,
        template=TaskSpec(name="tpl", needs=Resources(cpu=300, memory=300)),
    )
    sim.deploys.append(web)
    detector = Detector()

    for day in range(7):
        if day == 3:
            sim.deploys[0] = DeploySpec(
                name="web", replicas=14, template=web.template
            )
        if day == 5:
            sim.store.remove_task("web-0")
        sim.run(DAY)
        drifts = detector.correct(sim.store, [sim.deploys[0]], sim.deployer)
        report = violations(sim.store)
        print(
            f"day {day}: running {sim.running_count()}, "
            f"serving {sim.serving_count()}, nodes {len(sim.store.nodes)}, "
            f"drift corrected {len(drifts[0])}, invariants broken {len(report)}"
        )

    print()
    print(scrape(sim).render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
