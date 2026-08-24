from __future__ import annotations

from fleet.control.deploy import DeploySpec
from fleet.objects import Resources, TaskSpec
from fleet.sched.quota import Drf, Team
from fleet.sim.cluster import Script, Sim


def drf_pair() -> Drf:
    return Drf(
        capacity=Resources(cpu=9000, memory=18000),
        teams=[
            Team(name="cpuheavy", shape=Resources(cpu=100, memory=40)),
            Team(name="memheavy", shape=Resources(cpu=10, memory=200)),
        ],
    )


class TestDrf:
    def test_admissions_equalise_dominant_shares(self):
        drf = drf_pair()
        drf.run_dry()
        shares = [round(drf.dominant_share(team), 3) for team in drf.teams]
        assert shares[0] == shares[1] == 0.833

    def test_the_poorest_team_is_served_first(self):
        drf = drf_pair()
        drf.teams[0].admitted = 10
        assert drf.admit_next() == "memheavy"

    def test_admission_stops_at_capacity(self):
        drf = drf_pair()
        drf.run_dry()
        used = Resources.none()
        for team in drf.teams:
            used = used.plus(team.holding())
        assert used.fits_in(drf.capacity)
        assert drf.admit_next() is None

    def test_a_name_breaks_the_opening_tie(self):
        drf = drf_pair()
        assert drf.admit_next() == "cpuheavy"


class TestSim:
    def web(self, replicas: int = 6) -> DeploySpec:
        return DeploySpec(
            name="web",
            replicas=replicas,
            template=TaskSpec(name="tpl", needs=Resources(cpu=200, memory=200)),
        )

    def test_a_quiet_cluster_reaches_and_holds_the_count(self):
        sim = Sim()
        sim.add_nodes(3)
        sim.deploys.append(self.web())
        sim.run(20)
        assert sim.availability[0] == 6
        assert sim.worst_availability() == 6

    def test_a_silent_node_loses_its_tasks_to_the_others(self):
        sim = Sim(script=Script(silences={"n1": (30, 60)}))
        sim.add_nodes(3)
        sim.deploys.append(self.web())
        sim.run(80)
        assert sim.monitor.evicted == 2
        assert {task.node for task in sim.store.tasks.values()} == {"n0", "n2"}

    def test_the_sim_is_deterministic(self):
        def run() -> list[int]:
            sim = Sim(script=Script(silences={"n0": (10, 25)}))
            sim.add_nodes(3)
            sim.deploys.append(self.web())
            sim.run(40)
            return sim.availability

        assert run() == run()

    def test_an_overfull_ask_leaves_the_rest_pending(self):
        sim = Sim()
        sim.add_nodes(1)
        sim.deploys.append(self.web(replicas=9))
        sim.run(5)
        assert sim.running_count() == 5
        assert len(sim.store.pending_tasks()) == 4
