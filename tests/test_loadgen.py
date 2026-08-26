from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.loadgen import (
    RunReport,
    ScriptedServer,
    closed_loop,
    omission_gap,
    open_loop,
)


class TestTheServer:
    def test_service_time_is_the_floor(self):
        server = ScriptedServer(service_ticks=3)
        assert server.serve(arrival=0) == 3

    def test_a_busy_server_queues_the_next_arrival(self):
        server = ScriptedServer(service_ticks=3)
        server.serve(arrival=0)
        assert server.serve(arrival=1) == 6

    def test_a_stall_delays_the_start(self):
        server = ScriptedServer(service_ticks=2, stalls=((10, 20),))
        assert server.serve(arrival=12) == 22


class TestTheLoops:
    def test_the_closed_loop_paces_itself(self):
        report = closed_loop(ScriptedServer(service_ticks=2), duration=100)
        assert report.sent == 50
        assert report.percentile(0.99) == 2

    def test_the_open_loop_arrives_on_schedule(self):
        report = open_loop(
            ScriptedServer(service_ticks=2), duration=100, every=4
        )
        assert report.sent == 25

    def test_a_zero_interval_is_refused(self):
        with pytest.raises(Invalid):
            open_loop(ScriptedServer(service_ticks=1), duration=10, every=0)

    def test_no_completions_is_a_named_refusal(self):
        with pytest.raises(Invalid):
            RunReport(sent=0).percentile(0.5)


class TestCoordinatedOmission:
    def test_the_closed_loop_flatters_the_stall_thirtyfold(self):
        gap = omission_gap(
            service_ticks=2, stall=(100, 160), duration=300, every=4
        )
        assert gap["closed_p99"] == 2
        assert gap["open_p99"] == 60
        assert gap["flattery_factor"] == 30.0

    def test_the_closed_loop_hides_the_stall_in_throughput(self):
        gap = omission_gap(
            service_ticks=2, stall=(100, 160), duration=300, every=4
        )
        assert gap["closed_sent"] == 120
        no_stall = closed_loop(ScriptedServer(service_ticks=2), duration=300)
        assert no_stall.sent == 150

    def test_saturated_open_loop_never_drains(self):
        report = open_loop(
            ScriptedServer(service_ticks=2, stalls=((100, 160),)),
            duration=300,
            every=2,
        )
        assert report.percentile(0.5) == 62

    def test_the_report_line_reads_both_numbers(self):
        report = closed_loop(ScriptedServer(service_ticks=2), duration=10)
        assert report.line("closed") == "closed: 5 sent, p50 2, p99 2"
