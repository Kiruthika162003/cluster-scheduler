from __future__ import annotations

import pytest

from fleet.depends import DependencyGraph
from fleet.errors import Invalid
from fleet.riskscore import Change, RiskScorer


def wired() -> RiskScorer:
    graph = DependencyGraph()
    for service in ("web", "api", "search", "billing", "admin"):
        graph.declare(service, "db")
    graph.declare("web", "api")
    return RiskScorer(graph=graph)


def change(**overrides) -> Change:
    base = {
        "deploy": "db",
        "lines_changed": 5,
        "day_of_week": 1,
        "hour": 10,
        "recent_incidents": 0,
    }
    base.update(overrides)
    return Change(**base)


class TestScoring:
    def test_a_tiny_tuesday_change_rides_the_pipeline(self):
        scorer = wired()
        tiny = change(deploy="admin", lines_changed=5)
        assert scorer.band(tiny) == "low"
        assert scorer.requirements(tiny) == ["normal pipeline"]

    def test_blast_radius_is_scored_from_the_graph(self):
        scorer = wired()
        scorer.score(change(deploy="db"))
        assert ("5 deploys downstream", 3) in scorer.items

    def test_friday_night_is_hostile_twice(self):
        scorer = wired()
        risky = change(deploy="admin", day_of_week=4, hour=2)
        total = scorer.score(risky)
        assert ("shipping on a Friday", 2) in scorer.items
        assert ("shipping at 02:00", 2) in scorer.items
        assert total == 4

    def test_recent_incidents_compound(self):
        scorer = wired()
        scorer.score(change(deploy="admin", recent_incidents=2))
        assert ("2 recent incident(s) here", 4) in scorer.items

    def test_the_scheduler_rewrite_goes_critical(self):
        scorer = wired()
        big = change(
            deploy="db",
            lines_changed=800,
            day_of_week=4,
            recent_incidents=1,
        )
        assert scorer.band(big) == "critical"
        assert (
            "break-glass approval with a name and a reason"
            in scorer.requirements(big)
        )

    def test_nonsense_calendars_are_refused(self):
        with pytest.raises(Invalid):
            change(hour=25)
        with pytest.raises(Invalid):
            change(lines_changed=-1)


class TestTheReceipt:
    def test_every_point_is_a_line_item(self):
        scorer = wired()
        risky = change(deploy="db", lines_changed=200, day_of_week=4)
        page = scorer.receipt(risky)
        lines = page.splitlines()
        assert lines[0] == "db: high (7 points)"
        assert "  +2 200 lines changed" in lines
        assert "  +3 5 deploys downstream" in lines
        assert "  +2 shipping on a Friday" in lines
        assert "  requires: canary first" in lines
