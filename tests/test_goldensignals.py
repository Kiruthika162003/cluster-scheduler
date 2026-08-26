from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.goldensignals import DeploySignals, SignalBoard, SignalWindow


def feed(
    signals: DeploySignals,
    latencies: list[float],
    traffics: list[float],
    errors: float = 0.0,
    saturation: float = 0.3,
) -> None:
    for latency, traffic in zip(latencies, traffics, strict=True):
        signals.observe(
            latency=latency,
            traffic=traffic,
            errors=errors,
            saturation=saturation,
        )


class TestDirections:
    def test_a_short_window_stays_flat(self):
        window = SignalWindow()
        window.push(1.0)
        window.push(100.0)
        assert window.direction() == "flat"

    def test_a_doubling_reads_rising(self):
        window = SignalWindow()
        for value in (10, 10, 10, 20, 20, 20):
            window.push(float(value))
        assert window.direction() == "rising"

    def test_no_samples_is_refused(self):
        with pytest.raises(Invalid):
            SignalWindow().current()


class TestDiagnosis:
    def test_slow_and_flat_is_degrading(self):
        signals = DeploySignals()
        feed(signals, [10, 10, 10, 30, 30, 30], [100] * 6)
        assert signals.diagnosis().startswith("degrading")

    def test_slow_and_busier_is_growth(self):
        signals = DeploySignals()
        feed(signals, [10, 10, 10, 30, 30, 30], [100, 100, 100, 250, 250, 250])
        assert signals.diagnosis().startswith("growing into its limits")

    def test_errors_with_saturation_says_shed_first(self):
        signals = DeploySignals()
        feed(signals, [10] * 6, [100] * 6, errors=0.05, saturation=0.9)
        assert signals.diagnosis().startswith("erroring under load")

    def test_errors_without_pressure_is_a_bug(self):
        signals = DeploySignals()
        feed(signals, [10] * 6, [100] * 6, errors=0.05, saturation=0.2)
        assert "this is a bug, not capacity" in signals.diagnosis()

    def test_hot_but_holding_watches(self):
        signals = DeploySignals()
        feed(signals, [10] * 6, [100] * 6, saturation=0.85)
        assert signals.diagnosis().startswith("hot but holding")

    def test_boring_is_the_best_diagnosis(self):
        signals = DeploySignals()
        feed(signals, [10] * 6, [100] * 6)
        assert signals.diagnosis() == "healthy"

    def test_saturation_beyond_one_is_refused(self):
        with pytest.raises(Invalid):
            DeploySignals().observe(
                latency=1, traffic=1, errors=0, saturation=1.5
            )


class TestTheBoard:
    def test_the_page_names_only_the_troubled(self):
        board = SignalBoard()
        for _ in range(6):
            board.observe(
                "web", latency=10, traffic=100, errors=0.0, saturation=0.3
            )
            board.observe(
                "api", latency=10, traffic=100, errors=0.05, saturation=0.9
            )
        page = board.page()
        assert page.splitlines() == [
            "1 of 2 deploys need eyes",
            "  api: erroring under load: shed or scale, in that order",
        ]

    def test_an_all_quiet_board_says_so(self):
        board = SignalBoard()
        board.observe(
            "web", latency=10, traffic=100, errors=0.0, saturation=0.3
        )
        assert board.page() == "1 deploys, all healthy"
