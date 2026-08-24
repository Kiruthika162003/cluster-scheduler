"""Soft constraints: preferences have weights, and weights have prices.

A hard constraint refuses; a soft one just scores. The preference
scorer takes weighted wishes, prefer the ssd nodes, prefer the same
zone as the data, and the weight decides what the wish may cost in
packing quality. The measured page shows the trade as a curve: as the
preference weight climbs, wish satisfaction rises and consolidation
falls, and there is no weight at which both are best.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleet.objects import Node, Task
from fleet.sched.scorers import binpack


@dataclass(frozen=True)
class Wish:
    label: str
    value: str
    weight: float


def wish_scorer(wishes: tuple[Wish, ...]):
    def score(task: Task, node: Node, active: list[Task]) -> float:
        del task, active
        earned = 0.0
        for wish in wishes:
            if node.labels.get(wish.label) == wish.value:
                earned += wish.weight
        return earned

    return score


def blended(wishes: tuple[Wish, ...], preference_weight: float):
    """One scorer mixing consolidation and wishes at a chosen ratio."""
    wisher = wish_scorer(wishes)

    def score(task: Task, node: Node, active: list[Task]) -> float:
        return binpack(task, node, active) + preference_weight * wisher(
            task, node, active
        )

    return score


def satisfaction(store, wishes: tuple[Wish, ...]) -> float:
    """The share of active tasks whose node grants every wish."""
    active = store.active_tasks()
    if not active:
        return 0.0
    happy = 0
    for task in active:
        node = store.nodes[task.node]
        if all(node.labels.get(w.label) == w.value for w in wishes):
            happy += 1
    return happy / len(active)


def nodes_used(store) -> int:
    return len({task.node for task in store.active_tasks()})
