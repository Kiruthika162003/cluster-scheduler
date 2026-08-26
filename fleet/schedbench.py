"""Scheduler benchmarking: complexity is measured, never assumed.

The bigfleet trial pinned one data point; this harness draws the
curve. It runs the same scheduling workload at a ladder of fleet
sizes, counts filter evaluations rather than wall time so the curve
is deterministic and machine-independent, and fits the growth
exponent from the endpoints. The scheduler evaluates every node for
every task, so doubling nodes with tasks fixed should double the
work (exponent 1), and doubling both should quadruple it (exponent
2); a measured exponent above the model means someone added a loop
without telling the complexity budget, which is exactly what the
regression gate is for.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.store import Store


@dataclass(frozen=True)
class BenchPoint:
    nodes: int
    tasks: int
    evaluations: int


class _CountingFilter:
    __name__ = "counting_gate"

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, task, node, active):
        del task, node, active
        self.calls += 1


def _workload(node_count: int, task_count: int) -> tuple[Store, list[Task]]:
    store = Store()
    for number in range(node_count):
        store.add_node(
            Node(
                name=f"n{number}",
                capacity=Resources(cpu=10**9, memory=10**9),
            )
        )
    tasks = [
        Task(spec=TaskSpec(name=f"t{number}", needs=Resources(cpu=1, memory=1)))
        for number in range(task_count)
    ]
    return store, tasks


def measure(node_count: int, task_count: int) -> BenchPoint:
    store, tasks = _workload(node_count, task_count)
    counter = _CountingFilter()
    scheduler = Scheduler(filters=(counter,))
    for task in tasks:
        store.add_task(task)
        scheduler.schedule(store, task)
    return BenchPoint(
        nodes=node_count, tasks=task_count, evaluations=counter.calls
    )


@dataclass
class Bench:
    points: list[BenchPoint] = field(default_factory=list)

    def ladder(self, sizes: list[tuple[int, int]]) -> list[BenchPoint]:
        self.points = [measure(nodes, tasks) for nodes, tasks in sizes]
        return self.points

    def exponent(self) -> float:
        if len(self.points) < 2:
            raise Invalid("an exponent needs two points")
        first, last = self.points[0], self.points[-1]
        scale = (last.nodes * last.tasks) / (first.nodes * first.tasks)
        growth = last.evaluations / first.evaluations
        if scale <= 1:
            raise Invalid("the ladder must actually grow")
        return round(math.log(growth) / math.log(scale), 3)

    def regression_gate(self, budget_exponent: float = 1.0) -> tuple[bool, str]:
        measured = self.exponent()
        if measured <= budget_exponent + 0.05:
            return True, f"exponent {measured} within budget {budget_exponent}"
        return False, (
            f"exponent {measured} exceeds budget {budget_exponent}: "
            f"someone added a loop"
        )

    def table(self) -> str:
        lines = ["nodes  tasks  evaluations"]
        for point in self.points:
            lines.append(
                f"{point.nodes:>5}  {point.tasks:>5}  {point.evaluations:>11}"
            )
        return "\n".join(lines)
