"""Data gravity outvotes the spread scorer, and balance is priced in copies.

Four of six tasks claim volumes that live on n0. The spread scorer is
active and wants balance; the gravity filter refuses every node but the
data's home; and the cluster lands 4-1-1 with the scorer outvoted on
every claimed task. Rebalancing is not a scheduling decision: it costs
ten copy-ticks to move shard-b to n1, and only after the data moves do
the two tasks that claim it follow, settling the cluster at 2-2-1-1.
The scheduler never had the power; the volume book did.
"""

from __future__ import annotations

from collections import Counter

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.filters import EVERY_FILTER
from fleet.sched.scorers import spread
from fleet.store import Store
from fleet.trials.verdict import Verdict
from fleet.volumes import Volume, VolumeBook


def _cluster() -> tuple[Store, VolumeBook, Scheduler]:
    store = Store()
    for number in range(4):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=2000, memory=2000))
        )
    book = VolumeBook()
    book.add(Volume(name="shard-a", size=1000, home="n0"))
    book.add(Volume(name="shard-b", size=1000, home="n0"))
    scheduler = Scheduler(
        scorers=(spread,), filters=(*EVERY_FILTER, book.gravity_filter())
    )
    for number in range(6):
        task = Task(
            spec=TaskSpec(name=f"t{number}", needs=Resources(cpu=200, memory=200))
        )
        if number < 4:
            book.claim(
                f"t{number}", "shard-a" if number % 2 == 0 else "shard-b"
            )
        store.add_task(task)
    scheduler.schedule_pending(store)
    return store, book, scheduler


def run() -> Verdict:
    store, book, scheduler = _cluster()
    before = Counter(task.node for task in store.active_tasks())

    copy_ticks = book.migrate("shard-b", "n1")
    for name in ("t1", "t3"):
        task = store.get_task(name)
        generation = task.generation
        task.phase = "Pending"
        task.node = None
        store.update_task(task, read_generation=generation)
    scheduler.schedule_pending(store)
    after = Counter(task.node for task in store.active_tasks())

    numbers = {
        "before": dict(sorted(before.items())),
        "copy_ticks": copy_ticks,
        "after": dict(sorted(after.items())),
    }
    holds = (
        before == Counter({"n0": 4, "n1": 1, "n2": 1})
        and copy_ticks == 10
        and after == Counter({"n0": 2, "n1": 3, "n2": 1})
    )
    return Verdict(
        trial="datagravity",
        sentence=(
            "the spread scorer watches four claimed tasks pile onto the "
            "data's node, 4-1-1; ten copy-ticks move shard-b and only "
            "then do its two tasks follow to n1: rebalancing was never a "
            "scheduling decision, it was a copy"
        ),
        numbers=numbers,
        holds=holds,
    )
