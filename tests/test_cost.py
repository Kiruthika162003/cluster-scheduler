from __future__ import annotations

from fleet.sched.cost import (
    build_fleet,
    frugal_scorer,
    run_policy,
    value_scorer,
    workload,
)
from fleet.sched.scorers import binpack


class TestPricing:
    def test_only_occupied_nodes_are_billed(self):
        store, pricing = build_fleet()
        assert pricing.bill(store) == 0

    def test_the_bill_is_price_times_hours(self):
        store, pricing = run_policy((binpack,))[0:2]
        assert pricing.bill(store, hours=1) * 24 == pricing.bill(store, hours=24)


class TestPolicies:
    def test_every_policy_places_the_whole_workload(self):
        _, pricing = build_fleet()
        for scorers in (
            (frugal_scorer(pricing),),
            (binpack,),
            (value_scorer(pricing),),
        ):
            store, _, _ = run_policy(scorers)
            assert len(store.active_tasks()) == len(workload())

    def test_frugal_turns_on_the_most_machines(self):
        _, pricing = build_fleet()
        frugal_store, _, _ = run_policy((frugal_scorer(pricing),))
        value_store, _, _ = run_policy((value_scorer(pricing),))
        frugal_on = len({task.node for task in frugal_store.active_tasks()})
        value_on = len({task.node for task in value_store.active_tasks()})
        assert frugal_on > value_on

    def test_the_value_bill_survives_renaming(self):
        _, pricing_plain = build_fleet(False)
        _, _, plain = run_policy((value_scorer(pricing_plain),), False)
        _, pricing_flip = build_fleet(True)
        _, _, flipped = run_policy((value_scorer(pricing_flip),), True)
        assert plain == flipped

    def test_the_binpack_bill_does_not(self):
        _, _, plain = run_policy((binpack,), False)
        _, _, flipped = run_policy((binpack,), True)
        assert plain != flipped
