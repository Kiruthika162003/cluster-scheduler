"""Capacity holds: a per-node booking redeemed by tag at admission.

The broker in reservations.py answers the fleet-wide question; this
ledger answers the per-node one. A hold books part of one node for a
window of ticks, walk-in work may not push that node's free space
below the sum of active holds, and a task carrying the hold's tag
redeems it by name, on its node, inside its window. Overlapping holds
on one node must fit the node together or the second is refused at
write time, because the worst moment to discover an oversold window
is inside it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Conflict, Invalid, NotFound
from fleet.objects import Node, Resources, Task, free

HOLD_TAG = "fleet.hold"


@dataclass(frozen=True)
class Hold:
    name: str
    node: str
    amount: Resources
    starts: int
    ends: int

    def active_at(self, tick: int) -> bool:
        return self.starts <= tick < self.ends

    def overlaps(self, other: Hold) -> bool:
        return (
            self.node == other.node
            and self.starts < other.ends
            and other.starts < self.ends
        )


@dataclass
class HoldLedger:
    holds: dict[str, Hold] = field(default_factory=dict)

    def book(self, booking: Hold, node: Node) -> None:
        if booking.ends <= booking.starts:
            raise Invalid(f"{booking.name} has an empty window")
        if booking.name in self.holds:
            raise Conflict(f"{booking.name} is already booked")
        peak_cpu = booking.amount.cpu
        peak_memory = booking.amount.memory
        for other in self.holds.values():
            if other.overlaps(booking):
                peak_cpu += other.amount.cpu
                peak_memory += other.amount.memory
        if peak_cpu > node.capacity.cpu or peak_memory > node.capacity.memory:
            raise Conflict(
                f"{booking.name} would oversell {node.name}: "
                f"{peak_cpu}m peak against {node.capacity.cpu}m"
            )
        self.holds[booking.name] = booking

    def cancel(self, name: str) -> None:
        if name not in self.holds:
            raise NotFound(f"no booking named {name}")
        del self.holds[name]

    def held_on(self, node: str, tick: int) -> Resources:
        cpu = memory = 0
        for booking in self.holds.values():
            if booking.node == node and booking.active_at(tick):
                cpu += booking.amount.cpu
                memory += booking.amount.memory
        return Resources(cpu=cpu, memory=memory)

    def redeems(self, task: Task) -> str | None:
        return task.spec.labels.get(HOLD_TAG)

    def admits(
        self,
        task: Task,
        node: Node,
        tick: int,
        placed: list[Task] | None = None,
    ) -> tuple[bool, str]:
        claimed = self.redeems(task)
        if claimed is not None:
            booking = self.holds.get(claimed)
            if booking is None:
                return False, f"hold {claimed} does not exist"
            if booking.node != node.name:
                return False, f"hold {claimed} is on {booking.node}"
            if not booking.active_at(tick):
                return False, f"hold {claimed} is not active"
            return True, "redeeming the hold"
        held = self.held_on(node.name, tick)
        room = free(node, placed or [])
        if (
            room.cpu - task.spec.needs.cpu < held.cpu
            or room.memory - task.spec.needs.memory < held.memory
        ):
            return False, f"{held.cpu}m cpu is held"
        return True, "fits beside the held capacity"

    def expire(self, tick: int) -> list[str]:
        gone = sorted(
            name
            for name, booking in self.holds.items()
            if booking.ends <= tick
        )
        for name in gone:
            del self.holds[name]
        return gone

    def report(self, tick: int) -> str:
        lines = [f"{len(self.holds)} holds"]
        for name in sorted(self.holds):
            booking = self.holds[name]
            state = "active" if booking.active_at(tick) else (
                "upcoming" if booking.starts > tick else "expired"
            )
            lines.append(
                f"  {name}: {booking.amount.cpu}m on {booking.node} "
                f"[{booking.starts}, {booking.ends}) {state}"
            )
        return "\n".join(lines)
