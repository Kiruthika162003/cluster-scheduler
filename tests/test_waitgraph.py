from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.waitgraph import WaitGraph


def deadlocked() -> WaitGraph:
    graph = WaitGraph()
    graph.waits("gang-a", "quota", "needs 2 more slots")
    graph.waits("quota", "ns-batch", "waiting for release")
    graph.waits("ns-batch", "gang-a", "tasks hold its nodes")
    return graph


class TestEdges:
    def test_waiting_on_yourself_is_refused(self):
        with pytest.raises(Invalid):
            WaitGraph().waits("a", "a", "confusion")

    def test_release_removes_the_edge(self):
        graph = deadlocked()
        graph.released("quota", "ns-batch")
        assert graph.cycles() == []

    def test_a_chain_is_not_a_cycle(self):
        graph = WaitGraph()
        graph.waits("a", "b", "x")
        graph.waits("b", "c", "y")
        assert graph.cycles() == []
        assert "all making progress" in graph.report()


class TestCycles:
    def test_the_loop_is_named_in_order(self):
        assert deadlocked().cycles() == [["gang-a", "quota", "ns-batch"]]

    def test_a_two_party_deadlock_is_found(self):
        graph = WaitGraph()
        graph.waits("a", "b", "x")
        graph.waits("b", "a", "y")
        assert graph.cycles() == [["a", "b"]]

    def test_each_cycle_reports_once(self):
        graph = deadlocked()
        graph.waits("x", "y", "one")
        graph.waits("y", "x", "two")
        assert len(graph.cycles()) == 2

    def test_disjoint_waiters_do_not_pollute_the_cycle(self):
        graph = deadlocked()
        graph.waits("free-task", "gang-b", "unrelated")
        assert graph.cycles() == [["gang-a", "quota", "ns-batch"]]


class TestBlockedBehind:
    def test_hop_distances_reach_the_tail(self):
        graph = deadlocked()
        graph.waits("task-1", "gang-a", "in its namespace")
        graph.waits("task-2", "task-1", "ordered after")
        graph.waits("task-3", "task-2", "ordered after")
        stuck = graph.blocked_behind(["gang-a", "quota", "ns-batch"])
        assert stuck == {"task-1": 1, "task-2": 2, "task-3": 3}

    def test_unrelated_waiters_have_no_distance(self):
        graph = deadlocked()
        graph.waits("elsewhere", "someone", "different fight")
        stuck = graph.blocked_behind(["gang-a", "quota", "ns-batch"])
        assert "elsewhere" not in stuck


class TestReport:
    def test_the_report_shows_every_edge_with_its_reason(self):
        graph = deadlocked()
        graph.waits("task-1", "gang-a", "in its namespace")
        page = graph.report()
        assert page.startswith("1 deadlock(s)")
        assert "gang-a waits on quota (needs 2 more slots)" in page
        assert "task-1 is 1 hop(s) behind" in page
