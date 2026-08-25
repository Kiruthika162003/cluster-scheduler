from __future__ import annotations

import pytest

from fleet.conformance import EVERY_CHECK, Conformance
from fleet.conformance2 import SECOND_WAVE
from fleet.conformance3 import THIRD_WAVE


class TestChecks:
    @pytest.mark.parametrize(
        "check",
        (*EVERY_CHECK, *SECOND_WAVE, *THIRD_WAVE),
        ids=lambda c: c.__name__,
    )
    def test_the_check_passes(self, check):
        result = check()
        assert result.passed, f"{result.name}: {result.detail}"

    def test_every_check_carries_a_promise(self):
        for check in (*EVERY_CHECK, *SECOND_WAVE, *THIRD_WAVE):
            result = check()
            assert result.promise and result.name


class TestSuite:
    def test_run_covers_every_check(self):
        suite = Conformance()
        assert len(suite.run()) == (
            len(EVERY_CHECK) + len(SECOND_WAVE) + len(THIRD_WAVE)
        )

    def test_nothing_is_failing(self):
        suite = Conformance()
        suite.run()
        assert suite.failing() == []

    def test_the_report_reads_pass_by_pass(self):
        report = Conformance().report()
        assert report.count("[pass]") == (
            len(EVERY_CHECK) + len(SECOND_WAVE) + len(THIRD_WAVE)
        )
        assert report.endswith("0 failing")
