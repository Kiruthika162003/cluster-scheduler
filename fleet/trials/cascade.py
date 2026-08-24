"""Preemption cascades: arrival order multiplies evictions, batching stops it.

Priorities 1 through 5 arrive cheapest first on a one-node cluster that
holds two at a time. Each newcomer preempts the standing cheapest, which
was itself admitted a moment ago: the one-by-one order pays an eviction
per rung. The same five tasks admitted in one batch, highest priority
first, evict nobody, because the queue looked before it leapt.
"""

from __future__ import annotations

import contextlib

from fleet.errors import Unschedulable
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.preempt import Preemptor, requeue_evicted
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _cluster() -> Store:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    return store


def _task(priority: int) -> Task:
    return Task(
        spec=TaskSpec(
            name=f"p{priority}",
            needs=Resources(cpu=500, memory=500),
            priority=priority,
        )
    )


def _one_by_one() -> int:
    store = _cluster()
    scheduler = Scheduler()
    preemptor = Preemptor()
    for priority in (1, 2, 3, 4, 5):
        task = _task(priority)
        store.add_task(task)
        try:
            scheduler.schedule(store, task)
        except Unschedulable:
            preemptor.make_room(store, task)
            scheduler.schedule(store, task)
        requeue_evicted(store)
    return preemptor.evicted


def _batched() -> int:
    store = _cluster()
    scheduler = Scheduler()
    preemptor = Preemptor()
    for priority in (1, 2, 3, 4, 5):
        store.add_task(_task(priority))
    scheduler.schedule_pending(store)
    for task in store.pending_tasks():
        with contextlib.suppress(Unschedulable):
            preemptor.make_room(store, task)
    return preemptor.evicted


def run() -> Verdict:
    solo = _one_by_one()
    batch = _batched()
    numbers = {"evictions_one_by_one": solo, "evictions_batched": batch}
    holds = solo == 3 and batch == 0
    return Verdict(
        trial="cascade",
        sentence=(
            "cheapest-first arrival evicts 3 times to seat 5 tasks on 2 "
            "slots; the same tasks admitted as one priority-ordered batch "
            "evict nobody"
        ),
        numbers=numbers,
        holds=holds,
    )
