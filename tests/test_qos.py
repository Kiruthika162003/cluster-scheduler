from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.objects import Node, Resources
from fleet.sched.qos import Ask, PressureNode


def r(cpu: int, memory: int | None = None) -> Resources:
    return Resources(cpu=cpu, memory=memory if memory is not None else cpu)


def fresh() -> PressureNode:
    return PressureNode(node=Node(name="n0", capacity=r(1000)))


class TestAsk:
    def test_request_equal_to_limit_is_guaranteed(self):
        assert Ask("g", r(100), r(100)).klass() == "guaranteed"

    def test_request_below_limit_is_burstable(self):
        assert Ask("b", r(100), r(200)).klass() == "burstable"

    def test_no_request_is_besteffort(self):
        assert Ask("s", Resources.none(), r(200)).klass() == "besteffort"

    def test_request_past_limit_is_refused(self):
        with pytest.raises(Invalid):
            Ask("bad", r(200), r(100))


class TestAdmission:
    def test_admission_charges_requests_not_limits(self):
        node = fresh()
        assert node.admit(Ask("a", r(400), r(900)))
        assert node.admit(Ask("b", r(400), r(900)))

    def test_requests_past_capacity_are_refused(self):
        node = fresh()
        node.admit(Ask("a", r(700), r(700)))
        assert not node.admit(Ask("b", r(400), r(400)))

    def test_besteffort_always_fits_by_request(self):
        node = fresh()
        node.admit(Ask("a", r(1000), r(1000)))
        assert node.admit(Ask("s", Resources.none(), r(500)))


class TestBurstAndPressure:
    def test_burst_is_capped_at_the_limit(self):
        node = fresh()
        node.admit(Ask("b", r(100), r(300)))
        node.burst("b", r(900))
        assert node.usage() == r(300)

    def test_bursting_an_unknown_tenant_is_refused(self):
        with pytest.raises(Invalid):
            fresh().burst("ghost", r(1))

    def test_within_capacity_there_is_no_pressure(self):
        node = fresh()
        node.admit(Ask("b", r(100), r(800)))
        node.burst("b", r(800))
        assert not node.under_pressure()

    def test_simultaneous_bursts_create_pressure(self):
        node = fresh()
        node.admit(Ask("a", r(300), r(700)))
        node.admit(Ask("b", r(300), r(700)))
        node.burst("a", r(700))
        node.burst("b", r(700))
        assert node.under_pressure()


class TestEviction:
    def loaded(self) -> PressureNode:
        node = fresh()
        node.admit(Ask("g", r(400), r(400)))
        node.admit(Ask("burst-a", r(200), r(600)))
        node.admit(Ask("burst-b", r(200), r(600)))
        node.admit(Ask("scav", Resources.none(), r(400)))
        node.burst("burst-a", r(600))
        node.burst("burst-b", r(600))
        node.burst("scav", r(300))
        return node

    def test_besteffort_goes_first(self):
        node = self.loaded()
        assert node.relieve()[0] == "scav"

    def test_guaranteed_is_never_evicted(self):
        node = self.loaded()
        node.relieve()
        assert "g" in [tenant.ask.name for tenant in node.tenants]

    def test_relief_stops_at_capacity(self):
        node = self.loaded()
        node.relieve()
        assert not node.under_pressure()
        assert node.usage() == r(1000)

    def test_a_calm_node_evicts_nobody(self):
        node = fresh()
        node.admit(Ask("g", r(400), r(400)))
        assert node.relieve() == []

    def test_the_most_over_request_burstable_goes_first(self):
        node = fresh()
        node.admit(Ask("mild", r(300), r(500)))
        node.admit(Ask("wild", r(100), r(700)))
        node.burst("mild", r(500))
        node.burst("wild", r(700))
        assert node.relieve()[0] == "wild"
