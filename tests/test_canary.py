from __future__ import annotations

from fleet.roll.canary import MINIMUM_REQUESTS, Canary, Judge, Ledger


class TestLedger:
    def test_notes_accumulate(self):
        ledger = Ledger()
        ledger.note(100, 3)
        ledger.note(50, 1)
        assert ledger.requests == 150 and ledger.errors == 4

    def test_the_rate_of_nothing_is_zero(self):
        assert Ledger().rate() == 0.0


class TestJudge:
    def full(self, requests: int, errors: int) -> Ledger:
        ledger = Ledger()
        ledger.note(requests, errors)
        return ledger

    def test_too_little_evidence_keeps_watching(self):
        judge = Judge()
        ruling = judge.rule(self.full(10000, 100), self.full(MINIMUM_REQUESTS - 1, 50))
        assert ruling == "watch"

    def test_a_matching_canary_promotes(self):
        judge = Judge()
        ruling = judge.rule(self.full(10000, 100), self.full(400, 4))
        assert ruling == "promote"

    def test_a_worse_canary_within_tolerance_still_promotes(self):
        judge = Judge(tolerance=2.0)
        ruling = judge.rule(self.full(10000, 100), self.full(400, 7))
        assert ruling == "promote"

    def test_past_tolerance_rolls_back(self):
        judge = Judge(tolerance=2.0)
        ruling = judge.rule(self.full(10000, 100), self.full(400, 9))
        assert ruling == "rollback"

    def test_errors_against_a_perfect_stable_roll_back(self):
        judge = Judge()
        ruling = judge.rule(self.full(10000, 0), self.full(400, 1))
        assert ruling == "rollback"

    def test_a_perfect_canary_against_a_perfect_stable_promotes(self):
        judge = Judge()
        ruling = judge.rule(self.full(10000, 0), self.full(400, 0))
        assert ruling == "promote"


class TestCanary:
    def test_a_ruling_freezes_the_state(self):
        canary = Canary(traffic_share=0.5)
        while canary.state == "watching":
            canary.tick(1000, 0.01, 0.5)
        state = canary.state
        canary.tick(1000, 0.01, 0.0)
        assert canary.state == state == "rollback"

    def test_traffic_splits_by_share(self):
        canary = Canary(traffic_share=0.2)
        canary.tick(1000, 0.0, 0.0)
        assert canary.canary.requests == 200
        assert canary.stable.requests == 800
