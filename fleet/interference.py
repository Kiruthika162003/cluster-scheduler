"""Noisy neighbours: cpu overcommit degrades everyone, measured per tenant.

Requests reserve, but running tasks use what they use. When the sum of
actual use crosses the node's capacity, every tenant on the node slows
by the same factor, capacity over demand, because the kernel shares
fairly and fairness under scarcity means everybody loses together. The
meters show the two ways out: cap the noisy tenant at its request, or
move a victim, and what each one costs whom.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Tenant:
    name: str
    requested: int
    using: int
    capped: bool = False
    work_done: float = 0.0

    def demand(self) -> int:
        return min(self.using, self.requested) if self.capped else self.using


@dataclass
class SharedNode:
    capacity: int
    tenants: list[Tenant] = field(default_factory=list)

    def slowdown(self) -> float:
        demand = sum(tenant.demand() for tenant in self.tenants)
        if demand <= self.capacity:
            return 1.0
        return self.capacity / demand

    def tick(self) -> None:
        factor = self.slowdown()
        for tenant in self.tenants:
            tenant.work_done += tenant.demand() * factor

    def run(self, ticks: int) -> None:
        for _ in range(ticks):
            self.tick()

    def victim_throughput(self, name: str) -> float:
        for tenant in self.tenants:
            if tenant.name == name:
                return tenant.work_done
        raise KeyError(name)
