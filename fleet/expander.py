"""Expander strategies: which node to buy is a policy, not a reflex.

When pending work needs a new node, three reasonable teams buy
three different machines. Cheapest buys the lowest hourly price
that fits, and pays for it in fragmentation when the next task
does not fit the cheap box. Least-waste buys the box the demand
fills best, minimising stranded capacity at this instant. Priority
follows an ordered preference list, which is how organisations
encode contracts and reserved instances that no per-decision
arithmetic can see. The comparator runs all three against the same
demand and prices each choice in hourly cost and stranded cpu, so
the strategy argument happens over a table instead of over lunch.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass(frozen=True)
class NodeOffer:
    kind: str
    cpu: int
    hourly: int


@dataclass(frozen=True)
class Purchase:
    strategy: str
    kind: str
    hourly: int
    stranded_cpu: int

    def line(self) -> str:
        return (
            f"{self.strategy}: buy {self.kind} at {self.hourly}/h, "
            f"{self.stranded_cpu}m stranded"
        )


@dataclass
class Expander:
    offers: list[NodeOffer]
    preference: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.offers:
            raise Invalid("an expander needs offers to choose from")

    def _fitting(self, demand_cpu: int) -> list[NodeOffer]:
        fitting = [
            offer for offer in self.offers if offer.cpu >= demand_cpu
        ]
        if not fitting:
            raise Invalid(
                f"no offer fits {demand_cpu}m; the demand must be split"
            )
        return fitting

    def cheapest(self, demand_cpu: int) -> Purchase:
        chosen = min(
            self._fitting(demand_cpu),
            key=lambda offer: (offer.hourly, offer.cpu, offer.kind),
        )
        return Purchase(
            strategy="cheapest",
            kind=chosen.kind,
            hourly=chosen.hourly,
            stranded_cpu=chosen.cpu - demand_cpu,
        )

    def least_waste(self, demand_cpu: int) -> Purchase:
        chosen = min(
            self._fitting(demand_cpu),
            key=lambda offer: (offer.cpu - demand_cpu, offer.hourly, offer.kind),
        )
        return Purchase(
            strategy="least-waste",
            kind=chosen.kind,
            hourly=chosen.hourly,
            stranded_cpu=chosen.cpu - demand_cpu,
        )

    def by_priority(self, demand_cpu: int) -> Purchase:
        if not self.preference:
            raise Invalid("the priority strategy needs a preference list")
        fitting = {offer.kind: offer for offer in self._fitting(demand_cpu)}
        for kind in self.preference:
            if kind in fitting:
                chosen = fitting[kind]
                return Purchase(
                    strategy="priority",
                    kind=chosen.kind,
                    hourly=chosen.hourly,
                    stranded_cpu=chosen.cpu - demand_cpu,
                )
        raise Invalid("nothing on the preference list fits the demand")

    def compare(self, demand_cpu: int) -> str:
        rows = [self.cheapest(demand_cpu), self.least_waste(demand_cpu)]
        if self.preference:
            rows.append(self.by_priority(demand_cpu))
        return "\n".join(row.line() for row in rows)
