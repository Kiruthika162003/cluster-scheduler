from __future__ import annotations

import pytest

from fleet.depends import DependencyGraph
from fleet.errors import Invalid


def platform() -> DependencyGraph:
    graph = DependencyGraph()
    graph.declare("web", "api")
    graph.declare("api", "db")
    graph.declare("api", "cache")
    graph.declare("worker", "db")
    return graph


class TestDeclaration:
    def test_self_need_is_refused(self):
        with pytest.raises(Invalid):
            DependencyGraph().declare("web", "web")

    def test_a_cycle_is_refused_with_both_ends_named(self):
        graph = platform()
        with pytest.raises(Invalid) as caught:
            graph.declare("db", "web")
        assert "db needing web would close a cycle" in str(caught.value)

    def test_diamonds_are_fine(self):
        graph = platform()
        graph.declare("web", "cache")
        assert "cache" in graph.needs["web"]


class TestStartOrder:
    def test_needs_start_before_needers(self):
        order = platform().start_order()
        assert order.index("db") < order.index("api") < order.index("web")
        assert order.index("cache") < order.index("api")

    def test_ties_break_alphabetically(self):
        order = platform().start_order()
        assert order[:2] == ["cache", "db"]


class TestGating:
    def test_a_service_waits_for_its_needs_by_name(self):
        graph = platform()
        may, why = graph.may_start("api", running={"db"})
        assert not may and why == "waiting on cache"

    def test_met_needs_open_the_gate(self):
        graph = platform()
        may, why = graph.may_start("api", running={"db", "cache"})
        assert may and why == "all needs met"

    def test_a_leaf_service_starts_freely(self):
        may, _ = platform().may_start("db", running=set())
        assert may


class TestBlast:
    def test_a_db_failure_names_everything_downstream(self):
        assert platform().blast("db") == ["api", "web", "worker"]

    def test_a_cache_failure_spares_the_worker(self):
        assert platform().blast("cache") == ["api", "web"]

    def test_a_leaf_failure_hits_nobody(self):
        assert platform().blast("web") == []
