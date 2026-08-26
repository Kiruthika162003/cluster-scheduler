from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.scalerules import ScaleRules


class TestScalingUp:
    def test_a_modest_ask_is_granted_as_asked(self):
        rules = ScaleRules()
        assert rules.decide(0, current=4, desired=6) == 6
        assert rules.decisions[-1].rule == "as asked"

    def test_a_spike_is_step_limited(self):
        rules = ScaleRules(max_step_up=4)
        assert rules.decide(0, current=4, desired=40) == 8
        assert rules.decisions[-1].rule == "step limit"

    def test_the_ceiling_caps_even_patience(self):
        rules = ScaleRules(max_step_up=100, ceiling=10)
        assert rules.decide(0, current=8, desired=50) == 10
        assert rules.decisions[-1].rule == "ceiling"

    def test_repeated_steps_climb_to_the_ask(self):
        rules = ScaleRules(max_step_up=4)
        current = 4
        for tick in range(3):
            current = rules.decide(tick, current=current, desired=14)
        assert current == 14


class TestScalingDown:
    def test_the_first_low_reading_changes_nothing(self):
        rules = ScaleRules(stabilization=10)
        assert rules.decide(0, current=8, desired=2) == 8
        assert "stabilizing (10 to go)" in rules.decisions[-1].rule

    def test_the_window_must_pass_before_a_replica_leaves(self):
        rules = ScaleRules(stabilization=5)
        for tick in range(5):
            assert rules.decide(tick, current=8, desired=2) == 8
        assert rules.decide(5, current=8, desired=2) == 2
        assert rules.decisions[-1].rule == "stabilized down"

    def test_a_spike_inside_the_window_resets_the_clock(self):
        rules = ScaleRules(stabilization=5)
        for tick in range(4):
            rules.decide(tick, current=8, desired=2)
        rules.decide(4, current=8, desired=9)
        assert rules.decide(5, current=9, desired=2) == 9
        assert "stabilizing (5 to go)" in rules.decisions[-1].rule

    def test_the_floor_holds_under_zero_asks(self):
        rules = ScaleRules(stabilization=0, floor=2)
        assert rules.decide(0, current=5, desired=0) == 2
        assert rules.decisions[-1].rule == "floor"


class TestTheLedger:
    def test_bent_decisions_are_queryable(self):
        rules = ScaleRules(max_step_up=2)
        rules.decide(0, current=2, desired=10)
        rules.decide(1, current=4, desired=5)
        bent = rules.bent()
        assert len(bent) == 1
        assert bent[0].applied == 4

    def test_the_chart_marks_the_bends(self):
        rules = ScaleRules(max_step_up=2)
        rules.decide(0, current=2, desired=10)
        rules.decide(1, current=4, desired=4)
        chart = rules.chart().splitlines()
        assert chart[0].endswith("*")
        assert not chart[1].endswith("*")

    def test_a_backwards_interval_is_refused(self):
        with pytest.raises(Invalid):
            ScaleRules(floor=10, ceiling=5)
