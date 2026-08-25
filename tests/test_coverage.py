from __future__ import annotations

from fleet.control.budget import Budget
from fleet.coverage import (
    lint,
    unbudgeted_apps,
    unlabelled_tasks,
    unquotaed_namespaces,
    zoneless_nodes,
)
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store
from fleet.tenancyreport import standard_quota


def governed_store() -> Store:
    store = Store()
    store.add_node(
        Node(
            name="n0",
            capacity=Resources(cpu=1000, memory=1000),
            labels={"zone": "a"},
        )
    )
    task = Task(
        spec=TaskSpec(
            name="web-0",
            needs=Resources(cpu=100, memory=100),
            namespace="shop",
            labels=(("app", "web"),),
        )
    )
    task.bound_to("n0")
    store.add_task(task)
    return store


def full_governance() -> tuple[dict, list]:
    quotas = {"shop": standard_quota("shop", cpu=1000)}
    budgets = [
        Budget(
            name="web-floor",
            selector_key="app",
            selector_value="web",
            min_available=1,
        )
    ]
    return quotas, budgets


class TestCleanFleet:
    def test_full_coverage_lints_empty(self):
        quotas, budgets = full_governance()
        assert lint(governed_store(), quotas, budgets) == []


class TestGaps:
    def test_a_quotaless_namespace_is_named(self):
        findings = unquotaed_namespaces(governed_store(), {})
        assert findings == ["namespace shop runs work with no quota"]

    def test_finished_work_does_not_demand_a_quota(self):
        store = governed_store()
        store.get_task("web-0").phase = "Succeeded"
        assert unquotaed_namespaces(store, {}) == []

    def test_an_unbudgeted_app_is_named(self):
        findings = unbudgeted_apps(governed_store(), [])
        assert findings == ["app web has no disruption budget"]

    def test_a_zoneless_node_is_named(self):
        store = governed_store()
        store.add_node(Node(name="bare", capacity=Resources(cpu=1, memory=1)))
        assert zoneless_nodes(store) == ["node bare has no zone label"]

    def test_an_unlabelled_task_is_named(self):
        store = governed_store()
        loner = Task(spec=TaskSpec(name="loner", needs=Resources(cpu=1, memory=1)))
        loner.bound_to("n0")
        store.add_task(loner)
        assert unlabelled_tasks(store) == ["task loner carries no app label"]

    def test_the_lint_gathers_every_family(self):
        store = governed_store()
        store.add_node(Node(name="bare", capacity=Resources(cpu=1, memory=1)))
        findings = lint(store, {}, [])
        assert len(findings) == 3
