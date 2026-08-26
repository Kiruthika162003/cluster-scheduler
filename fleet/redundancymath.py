"""Redundancy arithmetic: chains multiply down, replicas multiply up.

A request that must pass the balancer, the app, and the database
succeeds only when all three do, so the chain's availability is
the product, always worse than its weakest link. Replicas invert
the story: the pair fails only when both halves do, so the
complement multiplies, and two mediocre nines make a good one.
The composition rules nest, which is how a real topology gets a
number instead of a shrug, and the marginal method answers the
budget question directly: given one more replica to spend, which
tier's addition buys the most availability, an answer that is
usually not the tier people feel worst about.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleet.errors import Invalid


def _checked(availability: float) -> float:
    """Composed values may round arbitrarily close to 1; raw inputs may not."""
    if not 0.0 < availability <= 1.0:
        raise Invalid("availability is a fraction between 0 and 1")
    return availability


def chain(*availabilities: float) -> float:
    if not availabilities:
        raise Invalid("an empty chain carries nothing")
    product = 1.0
    for availability in availabilities:
        product *= _checked(availability)
    return product


def replicas(availability: float, count: int) -> float:
    if count <= 0:
        raise Invalid("a tier needs at least one replica")
    if not 0.0 < availability < 1.0:
        raise Invalid("a single replica is strictly between 0 and 1")
    all_down = (1.0 - availability) ** count
    return 1.0 - all_down


@dataclass(frozen=True)
class Tier:
    name: str
    single: float
    count: int

    def __post_init__(self) -> None:
        if not 0.0 < self.single < 1.0:
            raise Invalid(f"{self.name}: a single replica is a fraction")

    def availability(self) -> float:
        return replicas(self.single, self.count)


def topology(tiers: list[Tier]) -> float:
    if not tiers:
        raise Invalid("a topology needs tiers")
    return chain(*(tier.availability() for tier in tiers))


def best_marginal_replica(tiers: list[Tier]) -> tuple[str, float]:
    """Which tier's next replica buys the most overall availability."""
    base = topology(tiers)
    best_name = None
    best_gain = 0.0
    for index, tier in enumerate(tiers):
        grown = [
            Tier(name=t.name, single=t.single, count=t.count + (index == i))
            for i, t in enumerate(tiers)
        ]
        gain = topology(grown) - base
        if gain > best_gain:
            best_gain = gain
            best_name = tier.name
    if best_name is None:
        raise Invalid("no replica anywhere helps; the chain is the problem")
    return best_name, round(best_gain, 8)


def statement(tiers: list[Tier]) -> str:
    lines = []
    for tier in tiers:
        lines.append(
            f"{tier.name}: {tier.count} x {tier.single} -> "
            f"{round(tier.availability(), 8)}"
        )
    lines.append(f"topology: {round(topology(tiers), 8)}")
    name, gain = best_marginal_replica(tiers)
    lines.append(f"next replica belongs in {name} (+{gain})")
    return "\n".join(lines)
