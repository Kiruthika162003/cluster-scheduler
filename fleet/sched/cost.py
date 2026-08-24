"""Money in the scorer: the cheapest node is not the cheapest cluster.

Nodes carry an hourly price. The frugal scorer sends every task to the
cheapest node with room, which fills the small cheap nodes first and
leaves the big expensive ones idling at full price for the tasks that
no longer fit anywhere else. The bill compares three policies over one
day of the same workload: frugal, packing by fullness, and packing by
price per unit of capacity, which is the one that actually minimises
the bill, because what costs money is the node being on, not the task
being placed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.objects import Node, Resources, Task, TaskSpec, allocated
from fleet.sched.core import Scheduler
from fleet.store import Store

PRICES = {"small": 10, "big": 32}
SHAPES = {"small": 1000, "big": 4000}


@dataclass
class Pricing:
    hourly: dict[str, int] = field(default_factory=dict)

    def price_of(self, node_name: str) -> int:
        return self.hourly[node_name]

    def bill(self, store: Store, hours: int = 24) -> int:
        """A node that hosts anything is on for the day; empty nodes are off."""
        active = store.active_tasks()
        occupied = {task.node for task in active}
        return sum(
            self.price_of(name) * hours for name in store.nodes if name in occupied
        )


def build_fleet(smalls_sort_first: bool = False) -> tuple[Store, Pricing]:
    store = Store()
    pricing = Pricing()
    for number in range(6):
        name = f"a-small-{number}" if smalls_sort_first else f"small-{number}"
        store.add_node(
            Node(name=name, capacity=Resources(cpu=SHAPES["small"], memory=4000))
        )
        pricing.hourly[name] = PRICES["small"]
    for number in range(2):
        name = f"big-{number}"
        store.add_node(
            Node(name=name, capacity=Resources(cpu=SHAPES["big"], memory=16000))
        )
        pricing.hourly[name] = PRICES["big"]
    return store, pricing


def frugal_scorer(pricing: Pricing):
    def score(task: Task, node: Node, active: list[Task]) -> float:
        del task, active
        return 1.0 / pricing.price_of(node.name)

    return score


def value_scorer(pricing: Pricing):
    """Prefer the node with the lowest price per cpu, then fuller."""

    def score(task: Task, node: Node, active: list[Task]) -> float:
        del task
        per_unit = pricing.price_of(node.name) / node.capacity.cpu
        used = allocated(node, active)
        fullness = used.cpu / node.capacity.cpu
        return (1.0 / per_unit) * 10 + fullness

    return score


def workload() -> list[TaskSpec]:
    sizes = [200] * 20 + [700] * 6
    return [
        TaskSpec(name=f"t{number:02d}", needs=Resources(cpu=size, memory=size))
        for number, size in enumerate(sizes)
    ]


def run_policy(scorers: tuple, smalls_sort_first: bool = False) -> tuple[Store, Pricing, int]:
    store, pricing = build_fleet(smalls_sort_first)
    scheduler = Scheduler(scorers=scorers)
    for spec in workload():
        store.add_task(Task(spec=spec))
    placed, stuck = scheduler.schedule_pending(store)
    del placed, stuck
    return store, pricing, pricing.bill(store)
