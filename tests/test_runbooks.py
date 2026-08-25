from __future__ import annotations

from fleet.api import Fleet
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.runbooks import Runbooks


def crowded_fleet() -> Fleet:
    fleet = Fleet()
    for number in range(2):
        fleet.store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    for number in range(2):
        fleet.submit(
            "setup",
            Task(
                spec=TaskSpec(
                    name=f"w{number}",
                    needs=Resources(cpu=400, memory=400),
                    labels=(("app", "web"),),
                )
            ),
        )
    fleet.step()
    return fleet


class TestDrainRunbook:
    def test_a_safe_drain_runs_and_reschedules(self):
        fleet = crowded_fleet()
        books = Runbooks()
        result = books.drain_node(fleet, "oncall", "n0")
        assert result.ran()
        assert any("rescheduled" in step for step in result.steps)

    def test_an_unsafe_drain_is_refused_before_any_step(self):
        fleet = crowded_fleet()
        fleet.store.get_node("n1").schedulable = False
        for name in ("w0", "w1"):
            held = fleet.store.get_task(name)
            generation = held.generation
            held.node = "n0"
            fleet.store.update_task(held, read_generation=generation)
        books = Runbooks()
        result = books.drain_node(fleet, "oncall", "n0")
        assert not result.ran()
        assert result.steps == []
        assert "no-go" in result.refused

    def test_the_refusal_is_journalled(self):
        fleet = crowded_fleet()
        Runbooks().drain_node(fleet, "oncall", "ghost")
        assert "runbook-refused" in fleet.journal.story("ghost")


class TestReplaceRunbook:
    def test_replace_provisions_retires_and_reschedules(self):
        fleet = crowded_fleet()
        result = Runbooks().replace_node(fleet, "oncall", "n0")
        assert result.ran()
        assert "n0" not in fleet.store.nodes
        assert "n0-replacement" in fleet.store.nodes

    def test_the_replacement_inherits_the_capacity(self):
        fleet = crowded_fleet()
        Runbooks().replace_node(fleet, "oncall", "n0")
        fresh = fleet.store.get_node("n0-replacement")
        assert fresh.capacity == Resources(cpu=1000, memory=1000)

    def test_replacing_a_ghost_refuses(self):
        fleet = crowded_fleet()
        assert not Runbooks().replace_node(fleet, "oncall", "ghost").ran()


class TestDrills:
    def test_a_clean_drill_says_whole(self):
        fleet = crowded_fleet()
        books = Runbooks()
        result = books.replace_node(fleet, "oncall", "n0")
        told = books.drill(fleet, "oncall", result)
        assert told.endswith("left the fleet whole")

    def test_a_refused_runbook_drills_as_correct(self):
        fleet = crowded_fleet()
        books = Runbooks()
        result = books.replace_node(fleet, "oncall", "ghost")
        assert "correctly refused" in books.drill(fleet, "oncall", result)
