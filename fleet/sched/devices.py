"""Device scheduling: accelerators are counted in slots, not millicores.

A GPU is not a divisible soup: a task takes whole devices, or a
declared fraction of one, and two tasks never share a whole device
by accident. The device pool tracks slots per node, placement takes
contiguity into account for jobs that want linked pairs, and the
anti-fragmentation rule protects the eight-slot boxes: a two-slot
job goes to the node whose free slots are fewest-but-sufficient,
because parking it on an empty eight-box strands six slots against
the day an eight-slot training job arrives. Fractional slices come
from a declared partition of one device and never straddle two,
since half a device on each of two cards is a bandwidth fiction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Conflict, Invalid, NotFound


@dataclass
class DeviceNode:
    name: str
    slots: int
    linked_pairs: tuple[tuple[int, int], ...] = ()
    used: set[int] = field(default_factory=set)
    slices: dict[int, list[str]] = field(default_factory=dict)

    def free_slots(self) -> list[int]:
        return [
            slot
            for slot in range(self.slots)
            if slot not in self.used and slot not in self.slices
        ]

    def free_linked_pair(self) -> tuple[int, int] | None:
        for left, right in self.linked_pairs:
            if left in self.free_slots() and right in self.free_slots():
                return (left, right)
        return None


@dataclass
class DevicePool:
    nodes: dict[str, DeviceNode] = field(default_factory=dict)
    placements: dict[str, tuple[str, tuple[int, ...]]] = field(
        default_factory=dict
    )

    def add_node(self, node: DeviceNode) -> None:
        if node.name in self.nodes:
            raise Conflict(f"{node.name} is already pooled")
        self.nodes[node.name] = node

    def place(self, task: str, count: int, linked: bool = False) -> str:
        if task in self.placements:
            raise Conflict(f"{task} already holds devices")
        if count <= 0:
            raise Invalid("a device ask must be positive")
        if linked and count != 2:
            raise Invalid("linked placement means a pair, exactly two")
        candidates = []
        for node in self.nodes.values():
            free = node.free_slots()
            if len(free) < count:
                continue
            if linked and node.free_linked_pair() is None:
                continue
            candidates.append((len(free), node.name))
        if not candidates:
            raise NotFound(f"no node has {count} free slots")
        candidates.sort()
        chosen = self.nodes[candidates[0][1]]
        if linked:
            pair = chosen.free_linked_pair()
            taken = pair
        else:
            taken = tuple(chosen.free_slots()[:count])
        for slot in taken:
            chosen.used.add(slot)
        self.placements[task] = (chosen.name, tuple(taken))
        return chosen.name

    def place_slice(self, task: str, node: str, share: int) -> int:
        """A slice occupies 1/share of one device; shares must match."""
        if share not in (2, 4, 8):
            raise Invalid("slices come in halves, quarters, or eighths")
        held = self.nodes.get(node)
        if held is None:
            raise NotFound(f"no node named {node}")
        for slot, tenants in held.slices.items():
            if len(tenants) < share:
                tenants.append(task)
                self.placements[task] = (node, (slot,))
                return slot
        free = held.free_slots()
        if not free:
            raise NotFound(f"{node} has no slot left to partition")
        slot = free[0]
        held.slices[slot] = [task]
        self.placements[task] = (node, (slot,))
        return slot

    def release(self, task: str) -> None:
        placed = self.placements.pop(task, None)
        if placed is None:
            raise NotFound(f"{task} holds no devices")
        node = self.nodes[placed[0]]
        for slot in placed[1]:
            node.used.discard(slot)
            if slot in node.slices:
                tenants = node.slices[slot]
                if task in tenants:
                    tenants.remove(task)
                if not tenants:
                    del node.slices[slot]

    def stranded_on_empty_boxes(self) -> int:
        return sum(
            node.slots
            for node in self.nodes.values()
            if not node.used and not node.slices and node.slots >= 8
        )

    def report(self) -> str:
        lines = []
        for name in sorted(self.nodes):
            node = self.nodes[name]
            free = len(node.free_slots())
            sliced = len(node.slices)
            lines.append(
                f"{name}: {free}/{node.slots} free"
                + (f", {sliced} partitioned" if sliced else "")
            )
        return "\n".join(lines)
