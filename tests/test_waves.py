from __future__ import annotations

from fleet.roll.waves import Delivery, Wave, standard


def run_healthy(delivery: Delivery, ticks: int) -> str:
    state = delivery.state
    for _ in range(ticks):
        state = delivery.tick(healthy=True)
    return state


class TestDelivery:
    def test_a_healthy_walk_delivers_after_the_bakes(self):
        delivery = Delivery(build="v1", waves=standard())
        assert run_healthy(delivery, 34) == "rolling"
        assert delivery.tick(healthy=True) == "delivered"

    def test_promotion_happens_in_order(self):
        delivery = Delivery(build="v1", waves=standard())
        run_healthy(delivery, 5)
        assert delivery.current().environment == "staging"
        run_healthy(delivery, 10)
        assert delivery.current().environment == "prod"

    def test_a_dev_failure_never_reaches_staging(self):
        delivery = Delivery(build="v1", waves=standard())
        run_healthy(delivery, 3)
        assert delivery.tick(healthy=False) == "aborted"
        assert delivery.reached() == ["dev"]

    def test_a_staging_failure_never_reaches_prod(self):
        delivery = Delivery(build="v1", waves=standard())
        run_healthy(delivery, 8)
        delivery.tick(healthy=False)
        assert "prod" not in delivery.reached()
        assert delivery.log[-1] == "staging: unhealthy, walk aborted"

    def test_an_aborted_delivery_stays_aborted(self):
        delivery = Delivery(build="v1", waves=standard())
        delivery.tick(healthy=False)
        assert delivery.tick(healthy=True) == "aborted"

    def test_a_delivered_build_reports_every_wave(self):
        delivery = Delivery(build="v1", waves=standard())
        run_healthy(delivery, 35)
        assert delivery.reached() == ["dev", "staging", "prod"]
        assert delivery.state == "delivered"

    def test_the_bake_resets_between_waves(self):
        delivery = Delivery(build="v1", waves=(Wave("a", 2), Wave("b", 3)))
        run_healthy(delivery, 2)
        assert delivery.baked == 0 and delivery.current().environment == "b"
