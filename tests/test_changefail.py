from __future__ import annotations

import pytest

from fleet.changefail import DeliveryLedger
from fleet.errors import Invalid, NotFound


def quarter() -> DeliveryLedger:
    ledger = DeliveryLedger()
    for number, lead in enumerate((10, 12, 8, 40, 11)):
        shipped = 100 + number * 50
        ledger.shipped(f"d{number}", committed=shipped - lead, shipped=shipped)
    ledger.failed("d3", noticed=260, restored=290)
    return ledger


class TestRecording:
    def test_shipping_before_committing_is_refused(self):
        with pytest.raises(Invalid):
            DeliveryLedger().shipped("d0", committed=10, shipped=5)

    def test_failures_must_link_to_a_deploy(self):
        with pytest.raises(NotFound):
            DeliveryLedger().failed("ghost", noticed=1, restored=2)

    def test_one_failure_per_deploy(self):
        ledger = quarter()
        with pytest.raises(Invalid):
            ledger.failed("d3", noticed=300, restored=310)


class TestTheFourKeys:
    def test_lead_time_is_a_median_not_a_mean(self):
        assert quarter().lead_time_median() == 11.0

    def test_frequency_is_deploys_over_the_window(self):
        assert quarter().frequency(window=250) == 0.02

    def test_failure_rate_comes_from_the_ledger(self):
        assert quarter().failure_rate() == 0.2

    def test_restore_time_averages_the_outages(self):
        assert quarter().restore_time_mean() == 30.0

    def test_the_scorecard_reads_all_four(self):
        page = quarter().scorecard(window=250)
        assert page.splitlines() == [
            "lead time (median): 11.0",
            "deploys per tick: 0.02",
            "change failure rate: 20%",
            "time to restore (mean): 30.0",
        ]

    def test_empty_ledgers_refuse_to_average(self):
        with pytest.raises(Invalid):
            DeliveryLedger().lead_time_median()


class TestTrends:
    def test_the_slowdown_arrives_with_numbers(self):
        ledger = DeliveryLedger()
        for number in range(3):
            ledger.shipped(f"early{number}", committed=0, shipped=10 + number)
        for number in range(3):
            ledger.shipped(
                f"late{number}", committed=100, shipped=140 + number
            )
        verdict = ledger.trend(split_at=100)
        assert verdict.startswith("slower: lead time 11 -> 41")

    def test_a_steady_team_reads_steady(self):
        ledger = DeliveryLedger()
        for number in range(4):
            ledger.shipped(f"d{number}", committed=0, shipped=10)
        assert ledger.trend(split_at=5) == (
            "not enough history on one side of the split"
        )
