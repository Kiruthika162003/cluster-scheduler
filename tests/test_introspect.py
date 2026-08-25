from __future__ import annotations

from fleet.control.nsquota import Admission, NamespaceQuota
from fleet.introspect import triage, why_pending
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.queue import SchedulingQueue
from fleet.store import Store


def cluster() -> Store:
    store = Store()
    for number in range(3):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    return store


def pending(name: str = "web", cpu: int = 100, **spec_extra) -> Task:
    return Task(
        spec=TaskSpec(
            name=name, needs=Resources(cpu=cpu, memory=cpu), **spec_extra
        )
    )


class TestTheWalk:
    def test_a_missing_task_is_the_first_gate(self):
        diagnosis = why_pending(cluster(), "ghost")
        assert diagnosis.verdict == "does not exist"
        assert diagnosis.fixable_by_owner

    def test_a_placed_task_is_not_pending(self):
        store = cluster()
        task = pending()
        task.bound_to("n0")
        store.add_task(task)
        diagnosis = why_pending(store, "web")
        assert diagnosis.verdict == "not pending"
        assert "already bound on n0" in diagnosis.detail

    def test_quota_speaks_before_the_filters(self):
        store = cluster()
        store.add_task(pending(namespace="search"))
        quotas = Admission(
            quotas={
                "search": NamespaceQuota(
                    namespace="search",
                    max_tasks=10,
                    max_requests=Resources(cpu=50, memory=50),
                )
            }
        )
        diagnosis = why_pending(store, "web", quotas=quotas)
        assert diagnosis.verdict == "held by quota"
        assert diagnosis.fixable_by_owner

    def test_the_bench_speaks_before_the_filters(self):
        store = cluster()
        store.add_task(pending())
        queue = SchedulingQueue()
        queue.offer("web", 100)
        queue.refuse("web", now=0)
        diagnosis = why_pending(store, "web", queue=queue, now=1)
        assert diagnosis.verdict == "benched with backoff"

    def test_an_oversized_task_names_the_fits_filter(self):
        store = cluster()
        store.add_task(pending(cpu=5000))
        diagnosis = why_pending(store, "web")
        assert diagnosis.verdict == "no node passes the filters"
        assert "fits on 3 nodes" in diagnosis.detail
        assert diagnosis.fixable_by_owner

    def test_a_schedulable_task_reports_its_takers(self):
        store = cluster()
        store.add_task(pending())
        diagnosis = why_pending(store, "web")
        assert diagnosis.verdict == "schedulable"
        assert "3 nodes would take it" in diagnosis.detail

    def test_cordons_point_at_the_platform(self):
        store = cluster()
        for node in store.nodes.values():
            node.schedulable = False
        store.add_task(pending())
        diagnosis = why_pending(store, "web")
        assert diagnosis.verdict == "no node passes the filters"
        assert not diagnosis.fixable_by_owner


class TestTriage:
    def test_the_page_holds_one_line_per_pending_task(self):
        store = cluster()
        store.add_task(pending("web"))
        store.add_task(pending("giant", cpu=9000))
        page = triage(store)
        assert page.startswith("2 pending")
        assert "giant: no node passes the filters" in page
        assert "web: schedulable" in page
