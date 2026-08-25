"""Why is my task pending: one question, every gate consulted, one page.

The explanation table in explain.py shows the filter and score math
for one scheduling pass; this asks the wider question an owner
actually types. The answer walks every gate in order: does the task
exist, is it already placed, is its namespace over quota, is it
benched with backoff, does any node pass the filters, and if nodes
pass, what is it waiting on. Each gate returns either a diagnosis
that ends the walk or a clean bill that moves to the next, so the
page always contains exactly one reason, the first one, which is the
only one worth reading when five things are wrong at once.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleet.control.nsquota import Admission
from fleet.errors import NotFound
from fleet.objects import Task
from fleet.sched.filters import EVERY_FILTER
from fleet.sched.queue import SchedulingQueue
from fleet.store import Store


@dataclass(frozen=True)
class Diagnosis:
    task: str
    verdict: str
    detail: str
    fixable_by_owner: bool

    def line(self) -> str:
        actor = "you" if self.fixable_by_owner else "the platform"
        return f"{self.task}: {self.verdict} ({self.detail}) [{actor} can fix]"


def _placement_verdict(store: Store, task: Task) -> Diagnosis:
    active = store.active_tasks()
    passing = 0
    refusals: dict[str, int] = {}
    for node in store.nodes.values():
        rejected = None
        for gate in EVERY_FILTER:
            if gate(task, node, active) is not None:
                rejected = gate.__name__
                break
        if rejected is None:
            passing += 1
        else:
            refusals[rejected] = refusals.get(rejected, 0) + 1
    if passing:
        return Diagnosis(
            task=task.spec.name,
            verdict="schedulable",
            detail=f"{passing} nodes would take it; waiting on the next pass",
            fixable_by_owner=False,
        )
    worst = max(sorted(refusals), key=lambda name: refusals[name])
    owner_fixable = worst in ("fits", "selector_matches", "tolerates_taints")
    return Diagnosis(
        task=task.spec.name,
        verdict="no node passes the filters",
        detail=f"most common refusal: {worst} on {refusals[worst]} nodes",
        fixable_by_owner=owner_fixable,
    )


def why_pending(
    store: Store,
    name: str,
    queue: SchedulingQueue | None = None,
    quotas: Admission | None = None,
    now: int = 0,
) -> Diagnosis:
    try:
        task = store.get_task(name)
    except NotFound:
        return Diagnosis(
            task=name,
            verdict="does not exist",
            detail="no task by that name; check the namespace and spelling",
            fixable_by_owner=True,
        )
    if task.node is not None:
        return Diagnosis(
            task=name,
            verdict="not pending",
            detail=f"already {task.phase.lower()} on {task.node}",
            fixable_by_owner=False,
        )
    if task.phase in ("Succeeded", "Failed"):
        return Diagnosis(
            task=name,
            verdict="not pending",
            detail=f"finished as {task.phase.lower()}",
            fixable_by_owner=False,
        )
    if quotas is not None:
        complaint = quotas.check(store, task)
        if complaint is not None:
            return Diagnosis(
                task=name,
                verdict="held by quota",
                detail=complaint,
                fixable_by_owner=True,
            )
    held = queue.waiting.get(name) if queue is not None else None
    if held is not None and held.benched_until > now:
        return Diagnosis(
            task=name,
            verdict="benched with backoff",
            detail="a recent pass failed; it retries when the bench expires",
            fixable_by_owner=False,
        )
    return _placement_verdict(store, task)


def triage(
    store: Store,
    queue: SchedulingQueue | None = None,
    quotas: Admission | None = None,
    now: int = 0,
) -> str:
    pending = sorted(
        task.spec.name
        for task in store.tasks.values()
        if task.node is None and task.phase == "Pending"
    )
    lines = [f"{len(pending)} pending"]
    for name in pending:
        lines.append(
            "  " + why_pending(store, name, queue, quotas, now).line()
        )
    return "\n".join(lines)
