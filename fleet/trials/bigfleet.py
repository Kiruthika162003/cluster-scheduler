"""The complexity receipt: what one pass costs at two hundred nodes.

The guess said placements would early-exit at the first passing node
and average five hundred filter calls per task. The meter said one
thousand, exactly nodes times filters, because the scheduler evaluates
every node for every task: scoring needs the whole candidate set, so
there is no early exit to have. Four hundred tasks cost 400000 filter
calls, deterministic to the digit, and the receipt exists so a
refactor that bends the curve, or an optimisation that finally caps
the candidate set, is named here first.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.filters import EVERY_FILTER
from fleet.store import Store
from fleet.trials.verdict import Verdict

NODES = 200
TASKS = 400


@dataclass
class CountedFilters:
    calls: int = 0
    wrapped: tuple = ()

    def wrap(self, filters: tuple) -> tuple:
        def counting(check):
            def counted(task, node, active):
                self.calls += 1
                return check(task, node, active)

            return counted

        return tuple(counting(check) for check in filters)


def run() -> Verdict:
    store = Store()
    for number in range(NODES):
        store.add_node(
            Node(
                name=f"n{number:03d}",
                capacity=Resources(cpu=1000, memory=1000),
            )
        )
    meter = CountedFilters()
    scheduler = Scheduler(filters=meter.wrap(EVERY_FILTER))
    for number in range(TASKS):
        store.add_task(
            Task(
                spec=TaskSpec(
                    name=f"t{number:03d}",
                    needs=Resources(cpu=450, memory=450),
                )
            )
        )
    placed, stuck = scheduler.schedule_pending(store)

    numbers = {
        "nodes": NODES,
        "tasks": TASKS,
        "placed": placed,
        "stuck": stuck,
        "filter_calls": meter.calls,
        "calls_per_task": meter.calls // TASKS,
    }
    holds = (
        placed == 400
        and stuck == 0
        and meter.calls == NODES * TASKS * 5
        and numbers["calls_per_task"] == 1000
    )
    return Verdict(
        trial="bigfleet",
        sentence=(
            "the guessed early exit does not exist: scoring wants every "
            "candidate, so four hundred placements cost exactly nodes "
            "times filters per task, 400000 calls to the digit, and the "
            "receipt will name the refactor that changes it"
        ),
        numbers=numbers,
        holds=holds,
    )
