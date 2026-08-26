from __future__ import annotations

import pytest

from fleet.cli import main


class TestCli:
    def test_trials_prints_the_report(self, capsys):
        assert main(["trials"]) == 0
        out = capsys.readouterr().out
        assert "fleet trials" in out and "0 broken" in out

    def test_check_passes_while_everything_holds(self, capsys):
        assert main(["check"]) == 0
        assert "all trials hold" in capsys.readouterr().out

    def test_a_command_is_required(self):
        with pytest.raises(SystemExit):
            main([])

    def test_bench_prints_the_curve_and_the_gate(self, capsys):
        assert main(["bench", "--sizes", "5x10,10x20"]) == 0
        out = capsys.readouterr().out
        assert "nodes  tasks  evaluations" in out
        assert "exponent 1.0 within budget 1.0" in out

    def test_summary_is_one_honest_line(self, capsys):
        assert main(["summary"]) == 0
        out = capsys.readouterr().out
        assert "trials (0 broken)" in out
        assert "conformance checks (0 failing)" in out
