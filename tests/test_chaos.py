from __future__ import annotations

from fleet.chaos import Chaos
from fleet.control.deploy import DeploySpec
from fleet.objects import Resources, TaskSpec
from fleet.sim.cluster import Script, Sim


class TestServingMeter:
    def quiet_sim(self) -> Sim:
        sim = Sim()
        sim.add_nodes(2)
        sim.deploys.append(
            DeploySpec(
                name="web",
                replicas=4,
                template=TaskSpec(name="tpl", needs=Resources(cpu=200, memory=200)),
            )
        )
        return sim

    def test_a_quiet_cluster_serves_what_it_runs(self):
        sim = self.quiet_sim()
        sim.run(10)
        assert sim.serving_count() == sim.running_count() == 4

    def test_a_dead_node_splits_the_meters(self):
        sim = Sim(script=Script(silences={"n0": (5, 999)}))
        sim.add_nodes(2)
        sim.deploys.append(
            DeploySpec(
                name="web",
                replicas=4,
                template=TaskSpec(name="tpl", needs=Resources(cpu=200, memory=200)),
            )
        )
        sim.run(12)
        assert sim.worst_serving(since=9) < sim.worst_availability(since=9)


class TestChaos:
    def test_a_storm_is_reproducible(self):
        one = Chaos()
        one.campaign(seeds=3)
        two = Chaos()
        two.campaign(seeds=3)
        assert [r.truthful for r in one.reports] == [r.truthful for r in two.reports]

    def test_the_campaign_floor_is_the_minimum(self):
        chaos = Chaos()
        floor = chaos.campaign(seeds=5)
        assert floor == min(report.truthful for report in chaos.reports)

    def test_the_worst_storm_matches_the_floor(self):
        chaos = Chaos()
        floor = chaos.campaign(seeds=5)
        assert chaos.worst_storm().truthful == floor

    def test_every_storm_records_its_silences(self):
        chaos = Chaos()
        chaos.campaign(seeds=4)
        assert all(report.silences for report in chaos.reports)


class TestProbeScripting:
    def test_scripted_probes_reach_the_keeper(self):
        sim = Sim(script=Script(failing_probes={"web-0": frozenset({0, 1})}))
        sim.add_nodes(1)
        sim.deploys.append(
            DeploySpec(
                name="web",
                replicas=1,
                template=TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100)),
            )
        )
        sim.wire_probes()
        sim.run(20)
        assert sim.keeper.restarts == 2
        assert sim.store.get_task("web-0").phase == "Running"

    def test_unscripted_probes_pass_immediately(self):
        sim = Sim()
        sim.add_nodes(1)
        sim.deploys.append(
            DeploySpec(
                name="web",
                replicas=1,
                template=TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100)),
            )
        )
        sim.wire_probes()
        sim.run(3)
        assert sim.keeper.restarts == 0
