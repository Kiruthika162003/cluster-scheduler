from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.expander import Expander, NodeOffer


def market(preference: list[str] | None = None) -> Expander:
    return Expander(
        offers=[
            NodeOffer(kind="small", cpu=2000, hourly=8),
            NodeOffer(kind="medium", cpu=4000, hourly=14),
            NodeOffer(kind="big", cpu=8000, hourly=30),
            NodeOffer(kind="reserved-medium", cpu=4000, hourly=20),
        ],
        preference=preference or [],
    )


class TestStrategies:
    def test_cheapest_takes_the_lowest_price_that_fits(self):
        purchase = market().cheapest(demand_cpu=1500)
        assert purchase.kind == "small"
        assert purchase.stranded_cpu == 500

    def test_cheapest_pays_in_stranding_when_demand_grows(self):
        purchase = market().cheapest(demand_cpu=2500)
        assert purchase.kind == "medium"
        assert purchase.stranded_cpu == 1500

    def test_least_waste_minimises_stranded_cpu(self):
        purchase = market().least_waste(demand_cpu=3900)
        assert purchase.kind == "medium"
        assert purchase.stranded_cpu == 100

    def test_least_waste_breaks_ties_by_price(self):
        purchase = market().least_waste(demand_cpu=4000)
        assert purchase.kind == "medium"
        assert purchase.hourly == 14

    def test_priority_encodes_the_contract(self):
        purchase = market(
            preference=["reserved-medium", "small"]
        ).by_priority(demand_cpu=1000)
        assert purchase.kind == "reserved-medium"

    def test_priority_falls_through_what_does_not_fit(self):
        purchase = market(
            preference=["small", "big"]
        ).by_priority(demand_cpu=5000)
        assert purchase.kind == "big"


class TestRefusals:
    def test_oversized_demand_is_a_named_refusal(self):
        with pytest.raises(Invalid, match="must be split"):
            market().cheapest(demand_cpu=10000)

    def test_priority_without_a_list_is_refused(self):
        with pytest.raises(Invalid):
            market().by_priority(demand_cpu=100)

    def test_an_exhausted_preference_list_is_named(self):
        with pytest.raises(Invalid, match="nothing on the preference list"):
            market(preference=["small"]).by_priority(demand_cpu=5000)

    def test_an_empty_market_is_refused(self):
        with pytest.raises(Invalid):
            Expander(offers=[])


class TestTheTable:
    def test_the_argument_happens_over_a_table(self):
        table = market(
            preference=["reserved-medium"]
        ).compare(demand_cpu=2500)
        assert table.splitlines() == [
            "cheapest: buy medium at 14/h, 1500m stranded",
            "least-waste: buy medium at 14/h, 1500m stranded",
            "priority: buy reserved-medium at 20/h, 1500m stranded",
        ]
