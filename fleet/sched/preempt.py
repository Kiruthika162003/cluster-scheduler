"""Preemption: the dear task moves in, the cheap ones move out, minimally.

When no node fits a high priority task, the scheduler asks what it would
cost to make room: on each node, which strictly cheaper tasks would have
to leave. It picks the node where the evicted priority sum is smallest,
breaking ties by fewest victims then node name, and it never evicts an
equal or higher priority, because a preemption loop wearing a scheduler
costume is still a loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Unschedulable
from fleet.objects import Node, Task, free
from fleet.store import Store


@dataclass
class Plan:
    node: str
    victims: tuple[str, ...]
    cost: int


@dataclass
class Preemptor:
    evicted: int = 0
    plans_made: int = 0
    log: list[Plan] = field(default_factory=list)

    def plan_for_node(
        self, task: Task, node: Node, active: list[Task]
    ) -> Plan | None:
        cheaper = sorted(
            (
                other
                for other in active
                if other.node == node.name
                and other.spec.priority < task.spec.priority
            ),
            key=lambda other: (other.spec.priority, other.spec.name),
        )
        room = free(node, active)
        needs = task.spec.needs
        victims: list[Task] = []
        for victim in cheaper:
            if needs.fits_in(room):
                break
            room = room.plus(victim.spec.needs)
            victims.append(victim)
        if not needs.fits_in(room):
            return None
        return Plan(
            node=node.name,
            victims=tuple(victim.spec.name for victim in victims),
            cost=sum(victim.spec.priority for victim in victims),
        )

    def best_plan(self, task: Task, nodes: list[Node], active: list[Task]) -> Plan | None:
        plans = []
        for node in nodes:
            plan = self.plan_for_node(task, node, active)
            if plan is not None:
                plans.append(plan)
        if not plans:
            return None
        self.plans_made += len(plans)
        return min(plans, key=lambda plan: (plan.cost, len(plan.victims), plan.node))

    def make_room(self, store: Store, task: Task) -> Plan:
        nodes = sorted(store.nodes.values(), key=lambda node: node.name)
        plan = self.best_plan(task, nodes, store.active_tasks())
        if plan is None:
            raise Unschedulable({"*": "no plan frees enough at lower priority"})
        for name in plan.victims:
            victim = store.get_task(name)
            generation = victim.generation
            victim.phase = "Evicted"
            victim.node = None
            store.update_task(victim, read_generation=generation)
            self.evicted += 1
        self.log.append(plan)
        return plan


def requeue_evicted(store: Store) -> int:
    """Evicted tasks go back to Pending; they were displaced, not wrong."""
    requeued = 0
    for task in list(store.tasks.values()):
        if task.phase == "Evicted":
            generation = task.generation
            task.phase = "Pending"
            store.update_task(task, read_generation=generation)
            requeued += 1
    return requeued

