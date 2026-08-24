"""Capacity planning: when the cluster runs out, axis by axis, and N+1.

Growth compounds per axis, and the axis that runs out first is rarely
the one being watched. The planner projects requested cpu and memory
under their own growth rates and names the day each crosses capacity.
The N+1 check asks a different question: not whether the fleet fits,
but whether it still fits after losing the largest node, because the
time to discover it does not is not during the loss.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleet.objects import Resources
from fleet.store import Store


@dataclass(frozen=True)
class Projection:
    axis: str
    used: int
    capacity: int
    daily_growth: float
    days_left: int | None

    def line(self) -> str:
        when = "never" if self.days_left is None else f"day {self.days_left}"
        return (
            f"{self.axis}: {self.used}/{self.capacity}, "
            f"{self.daily_growth:.1%}/day, full {when}"
        )


def _days_until(used: int, capacity: int, rate: float, horizon: int = 3650) -> int | None:
    if used >= capacity:
        return 0
    if rate <= 0:
        return None
    level = float(used)
    for day in range(1, horizon + 1):
        level *= 1 + rate
        if level >= capacity:
            return day
    return None


def project(store: Store, cpu_rate: float, memory_rate: float) -> list[Projection]:
    total = Resources.none()
    for node in store.nodes.values():
        total = total.plus(node.capacity)
    used = Resources.none()
    for task in store.active_tasks():
        used = used.plus(task.spec.needs)
    return [
        Projection(
            axis="cpu",
            used=used.cpu,
            capacity=total.cpu,
            daily_growth=cpu_rate,
            days_left=_days_until(used.cpu, total.cpu, cpu_rate),
        ),
        Projection(
            axis="memory",
            used=used.memory,
            capacity=total.memory,
            daily_growth=memory_rate,
            days_left=_days_until(used.memory, total.memory, memory_rate),
        ),
    ]


def survives_n_plus_one(store: Store) -> tuple[bool, str]:
    """Does the active workload fit after losing the largest node?"""
    if not store.nodes:
        return False, "no nodes"
    largest = max(
        store.nodes.values(), key=lambda node: (node.capacity.cpu, node.name)
    )
    remaining = Resources.none()
    for node in store.nodes.values():
        if node.name != largest.name:
            remaining = remaining.plus(node.capacity)
    used = Resources.none()
    for task in store.active_tasks():
        used = used.plus(task.spec.needs)
    if used.fits_in(remaining):
        return True, f"survives losing {largest.name}"
    short_cpu = max(0, used.cpu - remaining.cpu)
    short_memory = max(0, used.memory - remaining.memory)
    return False, (
        f"losing {largest.name} strands {short_cpu}m cpu "
        f"and {short_memory}Mi memory"
    )
