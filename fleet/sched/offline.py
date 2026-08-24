"""Offline packing: three greedy orders against the arithmetic floor.

Given every task up front, the packer chooses an order and a rule.
First-fit takes arrivals as they come; first-fit-decreasing sorts
largest first; best-fit puts each task where it leaves the least room.
The floor is the total demand divided by node size, rounded up: no
packer beats it, and the distance above it is the price of the order
chosen. The classic result shows up in the numbers: decreasing order is
worth more than a cleverer fit rule.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

NODE = 1000


@dataclass
class Packing:
    rule: str
    bins: list[int] = field(default_factory=list)

    def _first_fit(self, size: int) -> None:
        for at, used in enumerate(self.bins):
            if used + size <= NODE:
                self.bins[at] += size
                return
        self.bins.append(size)

    def _best_fit(self, size: int) -> None:
        best = -1
        tightest = NODE + 1
        for at, used in enumerate(self.bins):
            room = NODE - used
            if size <= room < tightest:
                best = at
                tightest = room
        if best < 0:
            self.bins.append(size)
        else:
            self.bins[best] += size

    def place(self, size: int) -> None:
        if self.rule == "best":
            self._best_fit(size)
        else:
            self._first_fit(size)


def pack(sizes: list[int], rule: str, decreasing: bool = False) -> Packing:
    packing = Packing(rule=rule)
    ordered = sorted(sizes, reverse=True) if decreasing else list(sizes)
    for size in ordered:
        packing.place(size)
    return packing


def floor_bins(sizes: list[int]) -> int:
    total = sum(sizes)
    return (total + NODE - 1) // NODE


def waste(packing: Packing) -> int:
    return sum(NODE - used for used in packing.bins)


def friendly_mix(seed: int = 11) -> list[int]:
    source = random.Random(seed)
    return [source.choice([120, 250, 330, 480, 610]) for _ in range(200)]


def adversarial_mix() -> list[int]:
    """A hundred 490s ahead of a hundred 510s: small-first is the trap."""
    return [490] * 100 + [510] * 100
