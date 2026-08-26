from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.retrybudget import RetryBudget


def earning(now: int = 0, count: int = 100) -> RetryBudget:
    budget = RetryBudget(ratio=0.1)
    for _ in range(count):
        budget.send()
        budget.succeeded(now)
    return budget


class TestEarning:
    def test_healthy_traffic_earns_retry_credit(self):
        budget = earning()
        grants = sum(budget.may_retry(1) for _ in range(20))
        assert grants == 10

    def test_first_attempts_are_never_budgeted(self):
        budget = RetryBudget(ratio=0.0)
        for _ in range(50):
            budget.send()
        assert budget.first_attempts == 50
        assert not budget.may_retry(0)

    def test_credit_ages_out_with_the_window(self):
        budget = earning(now=0)
        assert budget.may_retry(1)
        assert not budget.may_retry(30)

    def test_a_nonsense_ratio_is_refused(self):
        with pytest.raises(Invalid):
            RetryBudget(ratio=1.5)


class TestTheStorm:
    def test_an_outage_bankrupts_the_retries(self):
        budget = RetryBudget(ratio=0.1)
        for tick in range(10):
            budget.send()
            budget.succeeded(tick)
        granted = 0
        for tick in range(10, 40):
            budget.send()
            if budget.may_retry(tick):
                granted += 1
            if budget.may_retry(tick):
                granted += 1
        assert granted == 1
        assert budget.denied == 59

    def test_amplification_stays_near_the_ceiling(self):
        budget = RetryBudget(ratio=0.1)
        for tick in range(100):
            budget.send()
            budget.succeeded(tick)
            budget.may_retry(tick)
        assert budget.amplification() <= 1.11

    def test_the_naive_client_for_contrast(self):
        naive_sends = 100 * 3
        assert naive_sends / 100 == 3.0

    def test_the_statement_reads_the_three_numbers(self):
        budget = earning()
        budget.may_retry(1)
        line = budget.statement()
        assert "amplification" in line
        assert "1 retries in flight" in line
        assert "0 denied" in line

    def test_an_untouched_budget_amplifies_nothing(self):
        assert RetryBudget().amplification() == 1.0
