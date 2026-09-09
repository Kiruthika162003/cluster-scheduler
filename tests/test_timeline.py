from __future__ import annotations

from fleet.api import Fleet
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.timeline import phase_history, timeline


def storied_fleet() -> Fleet:
    fleet = Fleet()
    fleet.store.add_node(
        Node(name="n0", capacity=Resources(cpu=1000, memory=1000))
    )
    fleet.submit(
        "kiruthika",
        Task(
            spec=TaskSpec(
                name="batchling",
                needs=Resources(cpu=800, memory=800),
                priority=10,
            )
        ),
    )
    fleet.step()
    fleet.submit(
        "kiruthika",
        Task(
            spec=TaskSpec(
                name="crit", needs=Resources(cpu=800, memory=800), priority=1500
            )
        ),
    )
    fleet.step()
    return fleet


class TestTimeline:
    def test_the_page_merges_store_and_journal(self):
        fleet = storied_fleet()
        page = timeline(fleet.store, fleet.engine.journal, "batchling")
        assert "store: task-added" in page
        assert "engine: bind" in page
        assert "engine: displace" in page

    def test_the_page_ends_with_now_and_the_verdict(self):
        fleet = storied_fleet()
        page = timeline(fleet.store, fleet.engine.journal, "batchling")
        assert "now: Pending" in page
        assert "life was legal" in page

    def test_a_bound_task_shows_its_node(self):
        fleet = storied_fleet()
        page = timeline(fleet.store, fleet.engine.journal, "crit")
        assert "now: Bound on n0" in page

    def test_an_unknown_object_reads_gone(self):
        fleet = storied_fleet()
        page = timeline(fleet.store, fleet.engine.journal, "ghost")
        assert "nothing recorded" in page and "now: gone" in page

    def test_the_life_walks_the_displacement(self):
        fleet = storied_fleet()
        life = phase_history(fleet.engine.journal, fleet.store, "batchling")
        assert life == ["Pending", "Bound", "Evicted", "Pending"]
