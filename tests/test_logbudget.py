from __future__ import annotations

from fleet.logbudget import LogBudget


class TestUnderBudget:
    def test_everything_ships(self):
        budget = LogBudget(lines_per_window=10, window=100)
        for sequence in range(10):
            assert budget.offer("web", False, now=0, sequence=sequence)
        assert budget.shipped == 10
        assert budget.sampled_out == 0


class TestOverBudget:
    def test_the_overflow_is_sampled_and_stamped(self):
        budget = LogBudget(lines_per_window=10, window=100)
        shipped = 0
        for sequence in range(50):
            if budget.offer("chatty", False, now=1, sequence=sequence):
                shipped += 1
        assert shipped < 50
        assert budget.sampled_out == 50 - shipped
        assert budget.stamped and "sampling 1 in" in budget.stamped[0]

    def test_the_window_sliding_restores_full_shipping(self):
        budget = LogBudget(lines_per_window=5, window=10)
        for sequence in range(20):
            budget.offer("web", False, now=0, sequence=sequence)
        assert budget.offer("web", False, now=10, sequence=99)

    def test_budgets_are_per_namespace(self):
        budget = LogBudget(lines_per_window=5, window=100)
        for sequence in range(20):
            budget.offer("chatty", False, now=0, sequence=sequence)
        assert budget.offer("quiet", False, now=0, sequence=0)


class TestErrorExemption:
    def test_errors_ship_through_a_blown_budget(self):
        budget = LogBudget(lines_per_window=3, window=100)
        for sequence in range(30):
            budget.offer("web", False, now=0, sequence=sequence)
        assert budget.offer("web", True, now=0, sequence=99)

    def test_the_exemption_can_be_turned_off(self):
        budget = LogBudget(lines_per_window=1, window=100, exempt_errors=False)
        budget.offer("web", False, now=0, sequence=0)
        results = [
            budget.offer("web", True, now=0, sequence=sequence)
            for sequence in range(1, 9)
        ]
        assert not all(results)
