"""Node generations: the same request is not the same capacity.

The 2019 fleet runs a unit of work in three ticks; the 2024 fleet in
one. A scheduler that sees only requested cpu treats the generations
as interchangeable, and the work that lands on old iron simply takes
longer: same placement count, triple the finish time for the unlucky.
The profile-aware scorer weights nodes by speed and the finish-time
spread collapses. The meter that exposes the whole problem is not
utilisation, which looks identical either way, but the gap between the
fastest and slowest finisher of identical work.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.objects import Node, Resources, Task
from fleet.store import Store

SPEED_LABEL = "gen-speed"


def profiled_node(name: str, cpu: int, speed: int) -> Node:
    return Node(
        name=name,
        capacity=Resources(cpu=cpu, memory=cpu),
        labels={SPEED_LABEL: str(speed)},
    )


def speed_of(node: Node) -> int:
    return int(node.labels.get(SPEED_LABEL, "1"))


def speed_scorer():
    def score(task: Task, node: Node, active: list[Task]) -> float:
        del task, active
        return float(speed_of(node))

    return score


@dataclass
class WorkClock:
    """Ticks to finish identical work, per task, given its node's speed."""

    work_units: int
    finish_ticks: dict[str, int] = field(default_factory=dict)

    def measure(self, store: Store) -> dict[str, int]:
        for task in store.active_tasks():
            node = store.nodes[task.node]
            speed = speed_of(node)
            self.finish_ticks[task.spec.name] = -(-self.work_units // speed)
        return self.finish_ticks

    def spread(self) -> int:
        if not self.finish_ticks:
            return 0
        return max(self.finish_ticks.values()) - min(self.finish_ticks.values())
