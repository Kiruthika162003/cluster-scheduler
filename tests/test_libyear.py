from __future__ import annotations

import pytest

from fleet.errors import Invalid, NotFound
from fleet.libyear import FreshnessLedger, ReleaseHistory


def stocked() -> FreshnessLedger:
    ledger = FreshnessLedger()
    old = ledger.track("ancient-orm")
    old.released("1.0", at=0)
    old.released("2.0", at=200)
    old.released("3.0", at=400)
    fresh = ledger.track("http-client")
    fresh.released("9.0", at=350)
    fresh.released("9.1", at=390)
    ledger.pin("ancient-orm", "1.0")
    ledger.pin("http-client", "9.0")
    return ledger


class TestHistories:
    def test_age_is_newest_minus_yours(self):
        history = ReleaseHistory()
        history.released("1.0", at=0)
        history.released("2.0", at=150)
        assert history.age_behind("1.0") == 150
        assert history.age_behind("2.0") == 0

    def test_time_does_not_run_backwards(self):
        history = ReleaseHistory()
        history.released("1.0", at=100)
        with pytest.raises(Invalid):
            history.released("0.9", at=50)

    def test_the_never_released_are_named(self):
        history = ReleaseHistory()
        history.released("1.0", at=0)
        with pytest.raises(NotFound):
            history.age_behind("1.5")


class TestTheLedger:
    def test_libyears_score_the_manifest(self):
        assert stocked().libyears() == {
            "ancient-orm": 400,
            "http-client": 40,
        }

    def test_the_total_adds_the_volume_of_surprise(self):
        assert stocked().total() == 440

    def test_head_and_tail_need_different_meetings(self):
        head, tail = stocked().head_and_tail()
        assert head == 40
        assert tail == 400

    def test_pinning_the_untracked_is_refused(self):
        with pytest.raises(NotFound):
            FreshnessLedger().pin("ghost", "1.0")

    def test_an_empty_manifest_scores_nothing(self):
        with pytest.raises(Invalid):
            FreshnessLedger().libyears()

    def test_the_statement_marks_what_needs_a_plan(self):
        page = stocked().statement()
        assert page.splitlines() == [
            "440 libyears across 2 pins (head 40, tail 400)",
            "  ancient-orm: 400 behind [plan]",
            "  http-client: 40 behind",
        ]

    def test_repinning_refreshes_the_score(self):
        ledger = stocked()
        ledger.pin("ancient-orm", "3.0")
        assert ledger.libyears()["ancient-orm"] == 0
        assert ledger.total() == 40
