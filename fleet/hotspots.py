"""Hotspot detection: the busiest node is a fact, the fix is a diff.

Utilisation alone does not make a hotspot; a node is hot when it
runs meaningfully above the fleet mean while a cold peer has room,
because that pair is what a rebalance can actually exploit. The
first version aimed every move at the single coldest peer, and the
hotmoves trial caught the flaw: draining 400m into one partner made
the partner the new hotspot. The plan now spreads across every cold
peer, each capped at the hot margin so no target can cross the line
the survey itself draws. A report that names the moves is a plan; a
report that names only the temperature is a complaint.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleet.objects import Node, Task, allocated, free
from fleet.store import Store

HOT_MARGIN = 0.20


@dataclass(frozen=True)
class Move:
    task: str
    source: str
    target: str
    cpu: int


@dataclass(frozen=True)
class Hotspot:
    node: str
    share: float
    partner: str | None
    moves: tuple[Move, ...]

    def line(self) -> str:
        if self.partner is None:
            return (
                f"{self.node} at {self.share:.0%}: no viable partner, "
                f"add capacity or shed load"
            )
        if not self.moves:
            return (
                f"{self.node} at {self.share:.0%}: nothing movable fits "
                f"a cold peer, add capacity or shed load"
            )
        verb = ", ".join(
            f"move {move.task} ({move.cpu}m) to {move.target}"
            for move in self.moves
        )
        return f"{self.node} at {self.share:.0%}: {verb}"


def _share(node: Node, active: list[Task]) -> float:
    if node.capacity.cpu == 0:
        return 0.0
    return allocated(node, active).cpu / node.capacity.cpu


def _movable(node: Node, active: list[Task]) -> list[Task]:
    mine = [
        task
        for task in active
        if task.node == node.name and task.spec.priority < 100
    ]
    return sorted(mine, key=lambda task: (task.spec.needs.cpu, task.spec.name))


def survey(store: Store) -> list[Hotspot]:
    active = store.active_tasks()
    nodes = [node for node in store.nodes.values() if node.ready]
    if not nodes:
        return []
    mean = sum(_share(node, active) for node in nodes) / len(nodes)
    hot = [
        node
        for node in nodes
        if _share(node, active) - mean > HOT_MARGIN
    ]
    spots = []
    for node in sorted(hot, key=lambda n: -_share(n, active)):
        gap_cpu = int((_share(node, active) - mean) * node.capacity.cpu)
        partners = [
            candidate
            for candidate in sorted(
                nodes, key=lambda n: (_share(n, active), n.name)
            )
            if candidate.name != node.name
            and candidate.schedulable
            and _share(candidate, active) < mean
        ]
        partner = partners[0] if partners else None
        moves: list[Move] = []
        carried = 0
        remaining = _movable(node, active)
        for candidate in partners:
            ceiling = int((mean + HOT_MARGIN) * candidate.capacity.cpu)
            room = min(
                free(candidate, active).cpu,
                ceiling - allocated(candidate, active).cpu,
            )
            taken_here = 0
            left: list[Task] = []
            for task in remaining:
                cpu = task.spec.needs.cpu
                if carried + cpu > gap_cpu or taken_here + cpu > room:
                    left.append(task)
                    continue
                carried += cpu
                taken_here += cpu
                moves.append(
                    Move(
                        task=task.spec.name,
                        source=node.name,
                        target=candidate.name,
                        cpu=cpu,
                    )
                )
            remaining = left
            if not remaining:
                break
        spots.append(
            Hotspot(
                node=node.name,
                share=round(_share(node, active), 2),
                partner=partner.name if partner else None,
                moves=tuple(moves),
            )
        )
    return spots


def report(store: Store) -> str:
    spots = survey(store)
    if not spots:
        return "no hotspots: the fleet is within its margin"
    lines = [f"{len(spots)} hotspots"]
    for spot in spots:
        lines.append("  " + spot.line())
    return "\n".join(lines)
