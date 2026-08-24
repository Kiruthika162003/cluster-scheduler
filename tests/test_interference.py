from __future__ import annotations

import pytest

from fleet.interference import SharedNode, Tenant


def crowded(capped: bool) -> SharedNode:
    node = SharedNode(capacity=1000)
    node.tenants = [
        Tenant(name="a", requested=300, using=300),
        Tenant(name="noisy", requested=200, using=900, capped=capped),
    ]
    return node


class TestDemand:
    def test_an_uncapped_tenant_demands_its_use(self):
        assert Tenant(name="t", requested=200, using=900).demand() == 900

    def test_a_capped_tenant_demands_at_most_its_request(self):
        assert Tenant(name="t", requested=200, using=900, capped=True).demand() == 200

    def test_a_capped_underuser_demands_its_use(self):
        assert Tenant(name="t", requested=200, using=50, capped=True).demand() == 50


class TestSlowdown:
    def test_a_calm_node_runs_at_speed(self):
        node = SharedNode(capacity=1000)
        node.tenants = [Tenant(name="a", requested=300, using=300)]
        assert node.slowdown() == 1.0

    def test_scarcity_slows_by_the_ratio(self):
        assert crowded(capped=False).slowdown() == 1000 / 1200

    def test_the_cap_can_restore_full_speed(self):
        assert crowded(capped=True).slowdown() == 1.0

    def test_the_slowdown_applies_to_everyone(self):
        node = crowded(capped=False)
        node.tick()
        factor = 1000 / 1200
        assert node.victim_throughput("a") == pytest.approx(300 * factor)
        assert node.victim_throughput("noisy") == pytest.approx(900 * factor)


class TestWork:
    def test_work_accumulates_over_ticks(self):
        node = crowded(capped=True)
        node.run(10)
        assert node.victim_throughput("a") == pytest.approx(3000)

    def test_an_unknown_victim_raises(self):
        with pytest.raises(KeyError):
            crowded(capped=True).victim_throughput("ghost")
