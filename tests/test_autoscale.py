from __future__ import annotations

from fleet.autoscale import NodeScaler, ReplicaScaler


class TestReplicaScaler:
    def test_low_load_rests_at_the_floor(self):
        scaler = ReplicaScaler(floor=2, ceiling=20)
        assert scaler.wanted(2, load=50.0) == 2

    def test_load_moves_the_dial_up(self):
        scaler = ReplicaScaler(floor=2, ceiling=20)
        assert scaler.wanted(2, load=400.0) == 6

    def test_the_step_limit_dampens_the_climb(self):
        scaler = ReplicaScaler(floor=2, ceiling=20, step_limit=4)
        assert scaler.wanted(2, load=5000.0) == 6

    def test_the_ceiling_holds(self):
        scaler = ReplicaScaler(floor=2, ceiling=8, step_limit=100)
        assert scaler.wanted(2, load=10**6) == 8

    def test_descent_is_damped_too(self):
        scaler = ReplicaScaler(floor=2, ceiling=20, step_limit=4)
        assert scaler.wanted(18, load=100.0) == 14

    def test_decisions_are_recorded(self):
        scaler = ReplicaScaler(floor=1, ceiling=10)
        scaler.wanted(1, load=300.0)
        assert scaler.decisions == [(1, 5)]


class TestNodeScaler:
    def test_stuck_tasks_order_a_node(self):
        scaler = NodeScaler(warmup=3)
        assert scaler.observe_stuck(2, now=0) == []
        assert scaler.observe_stuck(0, now=3) == ["auto-0"]

    def test_no_stuck_means_no_order(self):
        scaler = NodeScaler()
        assert scaler.observe_stuck(0, now=0) == []
        assert scaler.provisioning == {}

    def test_warmup_delays_the_arrival(self):
        scaler = NodeScaler(warmup=5)
        scaler.observe_stuck(1, now=0)
        assert scaler.observe_stuck(0, now=4) == []
        assert scaler.observe_stuck(0, now=5) == ["auto-0"]

    def test_persistent_stuckness_orders_more_nodes(self):
        scaler = NodeScaler(warmup=2)
        scaler.observe_stuck(1, now=0)
        scaler.observe_stuck(1, now=1)
        arrived = scaler.observe_stuck(0, now=3)
        assert arrived == ["auto-0", "auto-1"]

    def test_a_brief_emptiness_retires_nothing(self):
        scaler = NodeScaler(scale_down_after=10)
        assert scaler.observe_empty(["n0"], now=0) == []
        assert scaler.observe_empty(["n0"], now=9) == []

    def test_sustained_emptiness_retires_the_node(self):
        scaler = NodeScaler(scale_down_after=10)
        scaler.observe_empty(["n0"], now=0)
        assert scaler.observe_empty(["n0"], now=10) == ["n0"]
        assert scaler.retired == 1

    def test_a_busy_interlude_resets_the_clock(self):
        scaler = NodeScaler(scale_down_after=10)
        scaler.observe_empty(["n0"], now=0)
        scaler.observe_empty([], now=5)
        assert scaler.observe_empty(["n0"], now=12) == []
