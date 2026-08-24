"""Overcommit and its bill: requests admit, limits burst, pressure evicts.

A task asks for a request it is guaranteed and a limit it may burst to.
The scheduler admits on requests, so a node's limits can sum past its
capacity; the gamble is that not everyone bursts at once. When they do,
the node is under pressure and evicts in class order: best-effort tasks
first, bursting burstables next, and guaranteed tasks never, because
their request is a contract and everything else was priced as a gamble.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.objects import Node, Resources


@dataclass(frozen=True)
class Ask:
    name: str
    request: Resources
    limit: Resources

    def __post_init__(self) -> None:
        if not self.request.fits_in(self.limit):
            raise Invalid(f"{self.name}: request exceeds limit")

    def klass(self) -> str:
        if self.request == Resources.none():
            return "besteffort"
        if self.request == self.limit:
            return "guaranteed"
        return "burstable"


@dataclass
class Tenancy:
    ask: Ask
    using: Resources


@dataclass
class PressureNode:
    node: Node
    tenants: list[Tenancy] = field(default_factory=list)
    evictions: list[str] = field(default_factory=list)

    def admit(self, ask: Ask) -> bool:
        requested = Resources.none()
        for tenant in self.tenants:
            requested = requested.plus(tenant.ask.request)
        if not requested.plus(ask.request).fits_in(self.node.capacity):
            return False
        self.tenants.append(Tenancy(ask=ask, using=ask.request))
        return True

    def burst(self, name: str, using: Resources) -> None:
        for tenant in self.tenants:
            if tenant.ask.name == name:
                capped = Resources(
                    cpu=min(using.cpu, tenant.ask.limit.cpu),
                    memory=min(using.memory, tenant.ask.limit.memory),
                )
                tenant.using = capped
                return
        raise Invalid(f"no tenant {name}")

    def usage(self) -> Resources:
        total = Resources.none()
        for tenant in self.tenants:
            total = total.plus(tenant.using)
        return total

    def under_pressure(self) -> bool:
        return not self.usage().fits_in(self.node.capacity)

    def _eviction_order(self) -> list[Tenancy]:
        def rank(tenant: Tenancy) -> tuple:
            klass = tenant.ask.klass()
            if klass == "besteffort":
                return (0, -tenant.using.memory, tenant.ask.name)
            over = tenant.using.memory - tenant.ask.request.memory
            return (1, -over, tenant.ask.name)

        return sorted(
            (t for t in self.tenants if t.ask.klass() != "guaranteed"), key=rank
        )

    def relieve(self) -> list[str]:
        """Evict until the node fits again; the evicted names, in order."""
        evicted = []
        for victim in self._eviction_order():
            if not self.under_pressure():
                break
            self.tenants.remove(victim)
            evicted.append(victim.ask.name)
        self.evictions.extend(evicted)
        return evicted
