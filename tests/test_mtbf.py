from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.mtbf import FailureLedger, Outage, allowed_downtime


def storied() -> FailureLedger:
    ledger = FailureLedger(subject="db")
    ledger.record(started=100, repaired=110)
    ledger.record(started=200, repaired=230)
    ledger.record(started=500, repaired=520)
    return ledger


class TestRecording:
    def test_a_repair_before_its_failure_is_refused(self):
        with pytest.raises(Invalid):
            Outage(started=10, repaired=10)

    def test_overlapping_outages_are_fiction(self):
        ledger = FailureLedger(subject="db")
        ledger.record(started=100, repaired=200)
        with pytest.raises(Invalid, match="break twice"):
            ledger.record(started=150, repaired=160)

    def test_out_of_order_recording_is_sorted(self):
        ledger = FailureLedger(subject="db")
        ledger.record(started=500, repaired=520)
        ledger.record(started=100, repaired=110)
        assert ledger.outages[0].started == 100


class TestAverages:
    def test_mttr_averages_the_actual_outages(self):
        assert storied().mttr() == 20.0

    def test_mtbf_averages_the_actual_gaps(self):
        assert storied().mtbf() == 180.0

    def test_one_outage_has_no_between(self):
        ledger = FailureLedger(subject="db")
        ledger.record(started=1, repaired=2)
        with pytest.raises(Invalid):
            ledger.mtbf()

    def test_no_outages_average_nothing(self):
        with pytest.raises(Invalid):
            FailureLedger(subject="db").mttr()


class TestAvailability:
    def test_downtime_is_subtracted_from_the_window(self):
        assert storied().availability(until=1000) == 0.94

    def test_an_ongoing_outage_counts_up_to_now(self):
        ledger = FailureLedger(subject="db")
        ledger.record(started=900, repaired=2000)
        assert ledger.availability(until=1000) == 0.9

    def test_the_statement_reads_the_quarter_honestly(self):
        assert storied().statement(until=1000) == (
            "db: 3 outages, 94.0000% available, mtbf 180.0, mttr 20.0"
        )

    def test_an_empty_window_is_refused(self):
        with pytest.raises(Invalid):
            FailureLedger(subject="db").availability(until=0)


class TestTheNines:
    def test_three_nines_is_43_minutes_a_month(self):
        assert allowed_downtime(0.999, window=43200) == 43

    def test_certainty_is_not_on_the_menu(self):
        with pytest.raises(Invalid):
            allowed_downtime(1.0, window=100)
