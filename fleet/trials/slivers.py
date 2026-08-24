"""Fragmentation priced in moves: two disruptions buy back a whole node.

Five nodes each holding one 400m task offer at most 600m to any
newcomer, though 3000m sits free. Two up-hill moves consolidate the
slivers and the largest placeable task goes from 600 to 1000, a whole
node bought for two disruptions. The rebalancer's own history is part
of the trial: the walk terminates with no move repeated, because both
of its termination bugs, the ping-pong and the frozen symmetric start,
were found by measuring exactly this cluster.
"""

from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.defrag import Rebalancer
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _sliver_city() -> Store:
    store = Store()
    for number in range(5):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
        task = Task(
            spec=TaskSpec(name=f"t{number}", needs=Resources(cpu=400, memory=400))
        )
        task.bound_to(f"n{number}")
        store.add_task(task)
    return store


def run() -> Verdict:
    store = _sliver_city()
    rebalancer = Rebalancer(budget=10)
    before = rebalancer.largest_placeable(store)
    spent = rebalancer.rebalance(store)
    after = rebalancer.largest_placeable(store)
    repeated = len(rebalancer.moves) != len(
        {(move.task, move.source, move.target) for move in rebalancer.moves}
    )

    numbers = {
        "free_cpu_total": 3000,
        "largest_before": before,
        "largest_after": after,
        "moves_spent": spent,
        "any_move_repeated": repeated,
    }
    holds = before == 600 and after == 1000 and spent == 2 and not repeated
    return Verdict(
        trial="slivers",
        sentence=(
            "3000m sits free but the largest welcome task is 600m until "
            "two up-hill moves consolidate the slivers and reopen a whole "
            "node; the walk repeats no move, which its first two drafts "
            "could not say"
        ),
        numbers=numbers,
        holds=holds,
    )
