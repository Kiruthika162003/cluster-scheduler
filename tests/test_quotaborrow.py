from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.quotaborrow import Lender


def pair() -> Lender:
    lender = Lender()
    lender.open_account("search", 1000)
    lender.open_account("ads", 600)
    return lender


class TestBorrowing:
    def test_use_within_the_guarantee_is_plain(self):
        lender = pair()
        assert lender.use("search", 800) == "search within guarantee"

    def test_overflow_borrows_from_the_idle_pool(self):
        lender = pair()
        lender.use("search", 600)
        assert lender.use("ads", 900) == "ads borrowed 300"
        assert lender.accounts["ads"].borrowed == 300

    def test_the_pool_cannot_be_overdrawn(self):
        lender = pair()
        lender.use("search", 800)
        with pytest.raises(Invalid) as caught:
            lender.use("ads", 900)
        assert "pool holds 200" in str(caught.value)

    def test_double_accounts_are_refused(self):
        lender = pair()
        with pytest.raises(Invalid):
            lender.open_account("search", 1)


class TestTheCall:
    def borrowed_world(self) -> Lender:
        lender = pair()
        lender.use("search", 600)
        lender.use("ads", 900)
        return lender

    def test_the_returning_owner_triggers_a_call_with_notice(self):
        lender = self.borrowed_world()
        told = lender.owner_returns("search", 400, now=10)
        assert told == ["ads called for 300, due 15"]

    def test_the_notice_window_is_honoured(self):
        lender = self.borrowed_world()
        lender.owner_returns("search", 400, now=10)
        assert lender.enforce(now=14) == []
        assert lender.enforce(now=15) == [
            "ads: 300 borrowed evicted at 15"
        ]

    def test_after_enforcement_the_books_balance(self):
        lender = self.borrowed_world()
        lender.owner_returns("search", 400, now=10)
        lender.enforce(now=15)
        assert lender.accounts["ads"].used == 600
        assert lender.accounts["ads"].borrowed == 0

    def test_a_return_inside_the_idle_pool_calls_nobody(self):
        lender = pair()
        lender.use("search", 600)
        lender.use("ads", 700)
        told = lender.owner_returns("search", 200, now=10)
        assert told == []

    def test_the_notice_window_is_an_oversubscribed_window(self):
        lender = self.borrowed_world()
        lender.owner_returns("search", 400, now=10)
        used_total = sum(held.used for held in lender.accounts.values())
        guaranteed_total = sum(
            held.guarantee for held in lender.accounts.values()
        )
        assert used_total > guaranteed_total
