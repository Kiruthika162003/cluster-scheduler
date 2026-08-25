from __future__ import annotations

import pytest

from fleet.errors import Invalid, NotFound
from fleet.tickets import ToilLedger


class TestLogging:
    def test_zero_minute_toil_is_a_contradiction(self):
        with pytest.raises(Invalid):
            ToilLedger().log(0, "meera", "cordon", 0, "n3 flapping")

    def test_small_toil_opens_no_candidate(self):
        ledger = ToilLedger()
        assert ledger.log(0, "meera", "cordon", 5, "n3") is None

    def test_the_threshold_opens_a_candidate_with_evidence(self):
        ledger = ToilLedger()
        ledger.log(0, "meera", "cordon", 20, "n3")
        candidate = ledger.log(5, "raj", "cordon", 15, "n9")
        assert candidate is not None
        assert candidate.minutes_seen == 35
        assert candidate.opened_at == 5

    def test_an_open_candidate_keeps_absorbing_minutes(self):
        ledger = ToilLedger()
        ledger.log(0, "meera", "cordon", 30, "n3")
        assert ledger.log(5, "raj", "cordon", 10, "n9") is None
        assert ledger.candidates["cordon"].minutes_seen == 40


class TestAutomation:
    def test_closing_requires_naming_the_robot(self):
        ledger = ToilLedger()
        ledger.log(0, "meera", "cordon", 30, "n3")
        ledger.automate("cordon", "quarantine warden")
        assert ledger.candidates["cordon"].closed_by == "quarantine warden"

    def test_closing_the_unopened_is_refused(self):
        with pytest.raises(NotFound):
            ToilLedger().automate("cordon", "robot")

    def test_double_closing_is_refused(self):
        ledger = ToilLedger()
        ledger.log(0, "meera", "cordon", 30, "n3")
        ledger.automate("cordon", "warden")
        with pytest.raises(Invalid):
            ledger.automate("cordon", "other robot")


class TestArithmetic:
    def test_minutes_beat_ticket_counts(self):
        ledger = ToilLedger()
        for number in range(10):
            ledger.log(number, "meera", "clicks", 1, "ack")
        ledger.log(20, "raj", "recovery", 30, "restore n5")
        assert ledger.worst() == "recovery"

    def test_the_report_orders_by_cost(self):
        ledger = ToilLedger()
        ledger.log(0, "meera", "cordon", 35, "n3")
        ledger.log(1, "raj", "restart", 10, "web-4")
        ledger.automate("cordon", "warden")
        page = ledger.report()
        assert page.startswith("45 manual minutes across 2 actions")
        lines = page.splitlines()
        assert "cordon: 35m [automated by warden]" in lines[1]
        assert "restart: 10m" in lines[2]

    def test_an_empty_ledger_has_no_worst(self):
        assert ToilLedger().worst() is None
