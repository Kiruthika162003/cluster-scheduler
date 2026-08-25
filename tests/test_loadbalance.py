from __future__ import annotations

from fleet.loadbalance import Balancer, Endpoint


def pair() -> list[Endpoint]:
    return [
        Endpoint(name="a", service_ticks=1),
        Endpoint(name="b", service_ticks=1),
    ]


class TestEndpoints:
    def test_service_drains_on_the_period(self):
        endpoint = Endpoint(name="slow", service_ticks=3)
        endpoint.offer()
        endpoint.work(now=1)
        assert endpoint.queue == 1
        endpoint.work(now=3)
        assert endpoint.queue == 0 and endpoint.served == 1


class TestPolicies:
    def test_round_robin_alternates(self):
        balancer = Balancer(policy="round-robin", endpoints=pair())
        assert balancer.pick().name == "a"
        assert balancer.pick().name == "b"
        assert balancer.pick().name == "a"

    def test_random_is_seeded_and_reproducible(self):
        one = Balancer(policy="random", endpoints=pair(), seed=3)
        two = Balancer(policy="random", endpoints=pair(), seed=3)
        assert [one.pick().name for _ in range(6)] == [
            two.pick().name for _ in range(6)
        ]

    def test_two_choices_takes_the_shorter_queue(self):
        endpoints = pair()
        endpoints[0].queue = 5
        balancer = Balancer(policy="two-choices", endpoints=endpoints)
        assert balancer.pick().name == "b"

    def test_worst_depth_is_tracked(self):
        balancer = Balancer(policy="round-robin", endpoints=pair())
        balancer.tick(now=1, arrivals=6)
        assert balancer.worst_depth >= 2

    def test_the_run_is_deterministic(self):
        def once() -> int:
            balancer = Balancer(policy="two-choices", endpoints=pair())
            for now in range(1, 50):
                balancer.tick(now, arrivals=3)
            return balancer.worst_depth

        assert once() == once()


class TestSlowStart:
    def test_the_ramp_weight_climbs_with_age(self):
        balancer = Balancer(
            policy="round-robin", endpoints=pair(), slow_start=10
        )
        newcomer = Endpoint(name="cold", service_ticks=1, joined_at=0)
        balancer.now = 1
        assert balancer._ramp_weight(newcomer) == 0.1
        balancer.now = 10
        assert balancer._ramp_weight(newcomer) == 1.0

    def test_without_slow_start_the_weight_is_flat(self):
        balancer = Balancer(policy="round-robin", endpoints=pair())
        newcomer = Endpoint(name="cold", service_ticks=1, joined_at=0)
        assert balancer._ramp_weight(newcomer) == 1.0

    def test_a_cold_period_slows_the_drain_then_lifts(self):
        endpoint = Endpoint(
            name="cold", service_ticks=1, joined_at=0, cold_period=5, cold_for=10
        )
        endpoint.offer()
        endpoint.work(now=3)
        assert endpoint.queue == 1
        endpoint.work(now=5)
        assert endpoint.queue == 0
        endpoint.offer()
        endpoint.work(now=11)
        assert endpoint.queue == 0
