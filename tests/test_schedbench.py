from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.schedbench import Bench, measure


class TestMeasurement:
    def test_evaluations_are_nodes_times_tasks(self):
        point = measure(node_count=10, task_count=20)
        assert point.evaluations == 200

    def test_the_count_is_deterministic(self):
        assert measure(5, 5).evaluations == measure(5, 5).evaluations


class TestTheCurve:
    def test_linear_scaling_measures_exponent_one(self):
        bench = Bench()
        bench.ladder([(10, 20), (20, 40)])
        assert bench.exponent() == 1.0

    def test_the_gate_passes_the_honest_scheduler(self):
        bench = Bench()
        bench.ladder([(10, 10), (40, 40)])
        passed, why = bench.regression_gate(budget_exponent=1.0)
        assert passed
        assert "within budget" in why

    def test_the_gate_catches_a_smuggled_loop(self):
        bench = Bench()
        bench.ladder([(10, 10), (40, 40)])
        doctored = bench.points[-1]
        bench.points[-1] = type(doctored)(
            nodes=doctored.nodes,
            tasks=doctored.tasks,
            evaluations=doctored.evaluations * 40,
        )
        passed, why = bench.regression_gate(budget_exponent=1.0)
        assert not passed
        assert "someone added a loop" in why

    def test_one_point_is_not_a_curve(self):
        bench = Bench()
        bench.ladder([(5, 5)])
        with pytest.raises(Invalid):
            bench.exponent()

    def test_a_flat_ladder_is_refused(self):
        bench = Bench()
        bench.ladder([(5, 5), (5, 5)])
        with pytest.raises(Invalid):
            bench.exponent()


class TestTheTable:
    def test_the_table_lines_up(self):
        bench = Bench()
        bench.ladder([(10, 20)])
        assert bench.table().splitlines() == [
            "nodes  tasks  evaluations",
            "   10     20          200",
        ]
