"""Interleaved gangs deadlock a cluster that rehearsed admission would share.

Two training jobs of six workers each, 500m apiece, on four 1000m nodes:
eight slots, twelve wanted. Admitting members alternately lands four of
each, the cluster is full, both jobs hold hostages and neither can ever
start. The rehearsing scheduler placed the first job whole, refused the
second whole, and the cluster runs one job now instead of zero forever.
Utilisation is identical in both worlds; throughput is not.
"""

from __future__ import annotations

import contextlib

from fleet.errors import Unschedulable
from fleet.objects import Node, Resources, Task
from fleet.sched.core import Scheduler
from fleet.sched.gang import Gang, GangScheduler, hostages
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _cluster() -> Store:
    store = Store()
    for number in range(4):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    return store


def _gangs() -> tuple[Gang, Gang]:
    shape = Resources(cpu=500, memory=500)
    return (
        Gang(name="train-a", members=6, each_needs=shape),
        Gang(name="train-b", members=6, each_needs=shape),
    )


def _interleaved() -> Store:
    store = _cluster()
    scheduler = Scheduler()
    first, second = _gangs()
    queues = [list(first.specs()), list(second.specs())]
    for round_at in range(6):
        for queue in queues:
            spec = queue[round_at]
            task = Task(spec=spec)
            store.add_task(task)
            with contextlib.suppress(Unschedulable):
                scheduler.schedule(store, task)
    return store


def run() -> Verdict:
    stuck = _interleaved()
    held = hostages(stuck)
    slots_hostaged = sum(held.values())

    rehearsed = _cluster()
    gang_scheduler = GangScheduler()
    first, second = _gangs()
    first_admitted = gang_scheduler.admit(rehearsed, first)
    second_admitted = gang_scheduler.admit(rehearsed, second)
    complete_jobs = int(first_admitted) + int(second_admitted)

    numbers = {
        "hostage_slots_interleaved": slots_hostaged,
        "gangs_hostaged": len(held),
        "complete_jobs_interleaved": 0,
        "complete_jobs_rehearsed": complete_jobs,
        "refused_whole": gang_scheduler.refused,
    }
    holds = (
        slots_hostaged == 8
        and len(held) == 2
        and complete_jobs == 1
        and gang_scheduler.refused == 1
    )
    return Verdict(
        trial="ganghostages",
        sentence=(
            "alternating admission fills all eight slots with hostages of "
            "two jobs that will never both start; rehearsing the whole "
            "gang first runs one job and refuses the other whole, same "
            "utilisation, infinite difference in throughput"
        ),
        numbers=numbers,
        holds=holds,
    )
