"""Scorers: among the nodes that said yes, which yes is best.

A scorer maps a passing node to a number, higher better, and the
scheduler sums the scorers it is given. Packing and spreading are the
same arithmetic with the sign flipped, which the pair of functions makes
plain rather than hiding behind two names that sound unrelated.
"""

from __future__ import annotations

from fleet.objects import Node, Task, allocated


def _fullness(node: Node, active: list[Task]) -> float:
    used = allocated(node, active)
    cpu_share = used.cpu / node.capacity.cpu if node.capacity.cpu else 1.0
    mem_share = used.memory / node.capacity.memory if node.capacity.memory else 1.0
    return (cpu_share + mem_share) / 2


def binpack(task: Task, node: Node, active: list[Task]) -> float:
    return _fullness(node, active)


def spread(task: Task, node: Node, active: list[Task]) -> float:
    return 1.0 - _fullness(node, active)


def peer_spread(task: Task, node: Node, active: list[Task]) -> float:
    """Fewer same-label peers on the node scores higher."""
    mine = task.spec.label_map().get("app")
    if mine is None:
        return 0.0
    peers = sum(
        1
        for other in active
        if other.node == node.name and other.spec.label_map().get("app") == mine
    )
    return 1.0 / (1 + peers)
