"""Chaos with a receipt: seeded storms, and the floor that held or did not.

A storm is a seeded schedule of node silences and probe failures thrown
at the simulated cluster. The harness runs many storms and reports the
worst availability seen across all of them, because a resilience claim
is a claim about the minimum over adversity, not the average over calm.
Every storm is reproducible from its seed: a floor that broke is a bug
report with the seed attached.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from fleet.control.deploy import DeploySpec
from fleet.objects import Resources, TaskSpec
from fleet.sim.cluster import Script, Sim


@dataclass
class StormReport:
    seed: int
    worst: int
    truthful: int
    evictions: int
    silences: dict[str, tuple[int, int]]


@dataclass
class Chaos:
    nodes: int = 5
    replicas: int = 8
    ticks: int = 120
    reports: list[StormReport] = field(default_factory=list)

    def _storm(self, seed: int) -> StormReport:
        source = random.Random(seed)
        silences: dict[str, tuple[int, int]] = {}
        victims = source.sample(range(self.nodes), k=source.randint(1, 2))
        for victim in victims:
            start = source.randint(20, 60)
            length = source.randint(15, 40)
            silences[f"n{victim}"] = (start, start + length)
        sim = Sim(script=Script(silences=silences))
        sim.add_nodes(self.nodes)
        sim.deploys.append(
            DeploySpec(
                name="web",
                replicas=self.replicas,
                template=TaskSpec(
                    name="tpl", needs=Resources(cpu=300, memory=300)
                ),
            )
        )
        sim.run(self.ticks)
        return StormReport(
            seed=seed,
            worst=sim.worst_availability(since=20),
            truthful=sim.worst_serving(since=20),
            evictions=sim.monitor.evicted,
            silences=silences,
        )

    def campaign(self, seeds: int) -> int:
        """Run seeded storms; returns the worst truthful serving anywhere."""
        for seed in range(seeds):
            self.reports.append(self._storm(seed))
        return min(report.truthful for report in self.reports)

    def worst_storm(self) -> StormReport:
        return min(self.reports, key=lambda report: (report.truthful, report.seed))
