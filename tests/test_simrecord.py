from __future__ import annotations

from fleet.control.deploy import DeploySpec
from fleet.objects import Resources, TaskSpec
from fleet.sim.cluster import Script, Sim
from fleet.simrecord import record


def stormy_sim() -> Sim:
    sim = Sim(script=Script(silences={"n1": (10, 25)}))
    sim.add_nodes(3)
    sim.deploys.append(
        DeploySpec(
            name="web",
            replicas=5,
            template=TaskSpec(name="tpl", needs=Resources(cpu=300, memory=300)),
        )
    )
    return sim


class TestDeterminism:
    def test_twin_runs_produce_identical_traces(self):
        one = record(stormy_sim(), ticks=40)
        two = record(stormy_sim(), ticks=40)
        assert one.first_divergence(two) is None

    def test_a_different_scenario_diverges_with_the_tick_named(self):
        calm = Sim()
        calm.add_nodes(3)
        calm.deploys.append(
            DeploySpec(
                name="web",
                replicas=5,
                template=TaskSpec(
                    name="tpl", needs=Resources(cpu=300, memory=300)
                ),
            )
        )
        stormy = record(stormy_sim(), ticks=40)
        peaceful = record(calm, ticks=40)
        divergence = stormy.first_divergence(peaceful)
        assert divergence is not None and divergence.startswith("tick")

    def test_length_mismatches_are_reported_not_ignored(self):
        long_trace = record(stormy_sim(), ticks=40)
        short_trace = record(stormy_sim(), ticks=20)
        assert "lengths differ" in long_trace.first_divergence(short_trace)


class TestPinnedTrace:
    def test_the_storm_trace_opening_is_pinned(self):
        trace = record(stormy_sim(), ticks=14)
        assert trace.rows[0] == (1, 5, 5, 3, 0)
        assert trace.rows[13] == (14, 5, 3, 3, 0)

    def test_the_eviction_shows_at_its_tick(self):
        trace = record(stormy_sim(), ticks=25)
        evictions = [row[4] for row in trace.rows]
        assert evictions[10] == 0
        assert evictions[-1] > 0
