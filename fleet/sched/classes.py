"""Priority classes: names with numbers, and a preemption matrix with edges.

Raw numbers invite arms races; classes are the treaty. Each class maps
to a band, system above critical above normal above batch above
scavenger, and the matrix answers one question: who may displace whom.
The two deliberate edges: nothing displaces system except system
itself, and batch may never displace anything, even scavengers, because
batch that preempts is batch that learned to jump the queue.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleet.errors import Invalid

BANDS = {
    "system": 10000,
    "critical": 1000,
    "normal": 100,
    "batch": 10,
    "scavenger": 0,
}


def number_for(klass: str) -> int:
    if klass not in BANDS:
        raise Invalid(f"unknown class {klass}")
    return BANDS[klass]


def class_of(priority: int) -> str:
    best = "scavenger"
    for name, floor in BANDS.items():
        if priority >= floor >= BANDS[best]:
            best = name
    return best


@dataclass(frozen=True)
class Verdicts:
    """The full matrix, precomputed and inspectable."""

    def may_displace(self, mover: str, victim: str) -> bool:
        for name in (mover, victim):
            if name not in BANDS:
                raise Invalid(f"unknown class {name}")
        if victim == "system":
            return mover == "system"
        if mover == "batch":
            return False
        return BANDS[mover] > BANDS[victim]

    def matrix(self) -> dict[tuple[str, str], bool]:
        names = sorted(BANDS, key=lambda name: -BANDS[name])
        return {
            (mover, victim): self.may_displace(mover, victim)
            for mover in names
            for victim in names
        }

    def rendered(self) -> str:
        names = sorted(BANDS, key=lambda name: -BANDS[name])
        width = max(len(name) for name in names) + 2
        lines = [" " * width + "  ".join(name.ljust(width) for name in names)]
        for mover in names:
            cells = [
                ("yes" if self.may_displace(mover, victim) else ".").ljust(width)
                for victim in names
            ]
            lines.append(mover.ljust(width) + "  ".join(cells))
        return "\n".join(lines)
