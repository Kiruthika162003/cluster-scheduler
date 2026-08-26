"""The hotspot report is a plan, and this trial made the plan honest.

A five-node fleet with one node at 90 percent and four at 20. The
first survey aimed all 400m of moves at the single coldest peer and
made that peer the new hotspot at 0.60: the plan halved the fire by
setting the neighbour alight. The planner now spreads across every
cold peer with each target capped at the hot margin, so the same
400m lands as two tasks on n1 and one on n2, n0 drops from 0.90 to
0.50, and the second survey finds nothing, which is the definition
of a plan that worked.
"""

from __future__ import annotations

from fleet.hotspots import survey
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _fleet() -> Store:
    store = Store()
    for number in range(5):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    sizes = (500, 200, 100, 100)
    for index, cpu in enumerate(sizes):
        task = Task(
            spec=TaskSpec(
                name=f"hot-{index}", needs=Resources(cpu=cpu, memory=cpu)
            )
        )
        task.bound_to("n0")
        store.add_task(task)
    for number in range(1, 5):
        task = Task(
            spec=TaskSpec(
                name=f"cold-{number}", needs=Resources(cpu=200, memory=200)
            )
        )
        task.bound_to(f"n{number}")
        store.add_task(task)
    return store


def _share(store: Store, node: str) -> float:
    used = sum(
        task.spec.needs.cpu
        for task in store.active_tasks()
        if task.node == node
    )
    return round(used / store.get_node(node).capacity.cpu, 2)


def run() -> Verdict:
    store = _fleet()
    before = survey(store)
    spot = before[0]
    for move in spot.moves:
        store.get_task(move.task).node = move.target
    after_share = _share(store, "n0")
    second_look = survey(store)
    numbers = {
        "hot_share_before": spot.share,
        "moved_cpu": sum(move.cpu for move in spot.moves),
        "hot_share_after": after_share,
        "hotspots_after": len(second_look),
    }
    targets = {move.target for move in spot.moves}
    numbers["distinct_targets"] = len(targets)
    holds = (
        spot.share == 0.9
        and numbers["moved_cpu"] == 400
        and after_share == 0.5
        and numbers["hotspots_after"] == 0
        and numbers["distinct_targets"] == 2
    )
    return Verdict(
        trial="hotmoves",
        sentence=(
            "the plan spreads 400m over two peers, n0 drops 0.90 to "
            "0.50, and the second survey finds nothing"
        ),
        numbers=numbers,
        holds=holds,
    )
