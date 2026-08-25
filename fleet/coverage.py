"""The coverage linter: every workload inside a policy, every gap named.

Policies protect only what they cover, and coverage erodes one
unlabelled deploy at a time. The linter cross-checks the fleet against
its own governance: namespaces running work without a quota, apps
without a disruption budget, nodes without a zone, deploys whose tasks
carry no app label at all. Findings are sentences with owners, and the
empty list is the deliverable, renewed every time governance or the
fleet changes shape.
"""

from __future__ import annotations

from fleet.control.budget import Budget
from fleet.control.nsquota import NamespaceQuota
from fleet.store import Store


def unquotaed_namespaces(
    store: Store, quotas: dict[str, NamespaceQuota]
) -> list[str]:
    running_spaces = {
        task.spec.namespace
        for task in store.tasks.values()
        if task.phase not in ("Succeeded", "Failed")
    }
    return sorted(
        f"namespace {space} runs work with no quota"
        for space in running_spaces - set(quotas)
    )


def unbudgeted_apps(store: Store, budgets: list[Budget]) -> list[str]:
    covered = {
        (budget.selector_key, budget.selector_value) for budget in budgets
    }
    apps = {
        task.spec.label_map().get("app")
        for task in store.tasks.values()
        if task.is_active() and task.spec.label_map().get("app")
    }
    return sorted(
        f"app {app} has no disruption budget"
        for app in apps
        if ("app", app) not in covered
    )


def zoneless_nodes(store: Store) -> list[str]:
    return sorted(
        f"node {name} has no zone label"
        for name, node in store.nodes.items()
        if "zone" not in node.labels
    )


def unlabelled_tasks(store: Store) -> list[str]:
    return sorted(
        f"task {task.spec.name} carries no app label"
        for task in store.tasks.values()
        if task.is_active() and "app" not in task.spec.label_map()
    )


def lint(
    store: Store,
    quotas: dict[str, NamespaceQuota],
    budgets: list[Budget],
) -> list[str]:
    findings: list[str] = []
    findings.extend(unquotaed_namespaces(store, quotas))
    findings.extend(unbudgeted_apps(store, budgets))
    findings.extend(zoneless_nodes(store))
    findings.extend(unlabelled_tasks(store))
    return findings
