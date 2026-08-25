from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.objects import Resources, Task, TaskSpec
from fleet.selector import matches, parse, select
from fleet.store import Store


def labelled(name: str, **labels: str) -> Task:
    return Task(
        spec=TaskSpec(
            name=name,
            needs=Resources(cpu=1, memory=1),
            labels=tuple(sorted(labels.items())),
        )
    )


class TestParsing:
    def test_equality_inequality_and_presence(self):
        clauses = parse("app=web, tier!=canary, gpu")
        assert [(c.key, c.op, c.value) for c in clauses] == [
            ("app", "=", "web"),
            ("tier", "!=", "canary"),
            ("gpu", "present", ""),
        ]

    def test_an_empty_clause_is_refused(self):
        with pytest.raises(Invalid):
            parse("app=web,,tier=x")

    def test_a_valueless_equality_is_refused(self):
        with pytest.raises(Invalid):
            parse("app=")

    def test_a_keyless_clause_is_refused(self):
        with pytest.raises(Invalid):
            parse("=web")


class TestMatching:
    def test_clauses_and_together(self):
        clauses = parse("app=web,tier!=canary")
        assert matches(clauses, {"app": "web", "tier": "stable"})
        assert not matches(clauses, {"app": "web", "tier": "canary"})
        assert not matches(clauses, {"app": "db", "tier": "stable"})

    def test_inequality_accepts_absence(self):
        clauses = parse("tier!=canary")
        assert matches(clauses, {})

    def test_presence_demands_the_key(self):
        clauses = parse("gpu")
        assert matches(clauses, {"gpu": "any"})
        assert not matches(clauses, {})


class TestSelect:
    def test_select_returns_sorted_matches(self):
        store = Store()
        store.add_task(labelled("web-b", app="web"))
        store.add_task(labelled("web-a", app="web"))
        store.add_task(labelled("db-0", app="db"))
        chosen = select(store, "app=web")
        assert [task.spec.name for task in chosen] == ["web-a", "web-b"]

    def test_a_compound_query_narrows(self):
        store = Store()
        store.add_task(labelled("stable", app="web", tier="stable"))
        store.add_task(labelled("canary", app="web", tier="canary"))
        chosen = select(store, "app=web,tier!=canary")
        assert [task.spec.name for task in chosen] == ["stable"]

    def test_no_matches_is_an_empty_list(self):
        assert select(Store(), "app=ghost") == []
