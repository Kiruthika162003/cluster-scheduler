from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.scenario import Cue, Expectation, Player
from fleet.sim.cluster import Sim


def sim_of(nodes: int = 3) -> Sim:
    sim = Sim()
    sim.add_nodes(nodes)
    return sim


class TestVocabulary:
    def test_unknown_verbs_are_refused_at_write_time(self):
        with pytest.raises(Invalid):
            Cue(0, "explode", ())

    def test_unknown_meters_are_refused_at_write_time(self):
        with pytest.raises(Invalid):
            Expectation(0, "vibes", 10)


class TestPlays:
    def test_scale_creates_then_resizes(self):
        sim = sim_of()
        player = Player(cues=[Cue(0, "scale", ("web", 4)), Cue(5, "scale", ("web", 2))])
        player.run(sim, ticks=10)
        assert sim.running_count() == 2

    def test_kill_and_heal_move_the_serving_meter(self):
        sim = sim_of()
        player = Player(
            cues=[
                Cue(0, "scale", ("web", 6)),
                Cue(10, "kill-node", ("n0",)),
                Cue(30, "heal-node", ("n0",)),
            ],
            expectations=[Expectation(50, "serving", 6)],
        )
        assert player.run(sim, ticks=60)

    def test_add_node_grows_the_fleet(self):
        sim = sim_of(nodes=1)
        player = Player(cues=[Cue(0, "add-node", ("fresh", 500))])
        player.run(sim, ticks=2)
        assert "fresh" in sim.store.nodes


class TestExpectations:
    def test_a_miss_reports_both_numbers(self):
        sim = sim_of()
        player = Player(
            cues=[Cue(0, "scale", ("web", 3))],
            expectations=[Expectation(5, "running", 99)],
        )
        assert not player.run(sim, ticks=10)
        assert player.misses == ["[5] running: expected 99, saw 3"]

    def test_a_passing_drill_reports_nothing(self):
        sim = sim_of()
        player = Player(
            cues=[Cue(0, "scale", ("web", 3))],
            expectations=[Expectation(5, "running", 3)],
        )
        assert player.run(sim, ticks=10)
        assert player.misses == []

    def test_the_full_drill_passes(self):
        sim = sim_of()
        player = Player(
            cues=[
                Cue(0, "scale", ("web", 6)),
                Cue(20, "kill-node", ("n1",)),
                Cue(50, "heal-node", ("n1",)),
                Cue(60, "add-node", ("extra", 1000)),
                Cue(60, "scale", ("web", 10)),
            ],
            expectations=[
                Expectation(10, "running", 6),
                Expectation(45, "serving", 6),
                Expectation(80, "running", 10),
                Expectation(80, "nodes", 4),
            ],
        )
        assert player.run(sim, ticks=90)
        assert sim.monitor.evicted == 2
