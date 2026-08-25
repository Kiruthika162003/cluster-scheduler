"""Node shapes against the workload mix: the stranded axis pays the bill.

A cpu-heavy workload lands on balanced nodes: every node exhausts its
cpu with most of its memory untouched, and the fleet reads full while
half its memory is stranded, unreachable by any task because the other
axis is gone. The same workload on cpu-heavy nodes shaped like it
strands almost nothing. Shape mismatch is invisible in node counts and
cpu totals, and the memory the balanced fleet strands, 9600 of 16000,
sixty percent of everything bought, is powered and unreachable until
the workload changes shape.
"""

from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _fleet(cpu: int, memory: int, count: int) -> Store:
    store = Store()
    for number in range(count):
        store.add_node(
            Node(
                name=f"n{number}",
                capacity=Resources(cpu=cpu, memory=memory),
            )
        )
    return store


def _place_until_stuck(store: Store) -> tuple[int, int]:
    scheduler = Scheduler()
    placed = 0
    number = 0
    while True:
        task = Task(
            spec=TaskSpec(
                name=f"t{number}", needs=Resources(cpu=500, memory=200)
            )
        )
        store.add_task(task)
        done, stuck = scheduler.schedule_pending(store)
        if stuck:
            store.remove_task(task.spec.name)
            break
        placed += done
        number += 1
    stranded_memory = 0
    active = store.active_tasks()
    for node in store.nodes.values():
        used_cpu = sum(
            t.spec.needs.cpu for t in active if t.node == node.name
        )
        used_memory = sum(
            t.spec.needs.memory for t in active if t.node == node.name
        )
        if node.capacity.cpu - used_cpu < 500:
            stranded_memory += node.capacity.memory - used_memory
    return placed, stranded_memory


def run() -> Verdict:
    balanced = _fleet(cpu=2000, memory=2000, count=8)
    balanced_placed, balanced_stranded = _place_until_stuck(balanced)

    shaped = _fleet(cpu=4000, memory=1600, count=4)
    shaped_placed, shaped_stranded = _place_until_stuck(shaped)

    numbers = {
        "cpu_either_fleet": 16000,
        "placed_balanced": balanced_placed,
        "stranded_memory_balanced": balanced_stranded,
        "placed_shaped": shaped_placed,
        "stranded_memory_shaped": shaped_stranded,
    }
    holds = (
        balanced_placed == shaped_placed == 32
        and balanced_stranded == 9600
        and shaped_stranded == 0
    )
    return Verdict(
        trial="strandedmemory",
        sentence=(
            "the same 16000m of cpu places the same 32 tasks either way, "
            "and the balanced fleet strands 9600Mi of memory behind "
            "exhausted cpu while the workload-shaped fleet strands zero: "
            "shape mismatch is invisible in every total except the one "
            "that was bought and can never be used"
        ),
        numbers=numbers,
        holds=holds,
    )
