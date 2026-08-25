from __future__ import annotations

from fleet.costanomaly import anomalies, attribution
from fleet.metering import Meter


def meter_of(**cpu_ticks: int) -> Meter:
    meter = Meter()
    meter.cpu_ticks = dict(cpu_ticks)
    return meter


class TestAnomalies:
    def test_steady_spend_reports_nothing(self):
        before = meter_of(search=1000, ads=500)
        after = meter_of(search=1100, ads=520)
        assert anomalies(before, after) == []

    def test_a_jump_names_the_team_and_the_numbers(self):
        before = meter_of(search=1000)
        after = meter_of(search=9000)
        assert anomalies(before, after) == ["search: up 800%, 1000 to 9000"]

    def test_a_collapse_reads_down(self):
        before = meter_of(ads=800)
        after = meter_of(ads=200)
        assert anomalies(before, after) == ["ads: down 75%, 800 to 200"]

    def test_new_and_vanished_spend_are_called_out(self):
        before = meter_of(old=100)
        after = meter_of(fresh=300)
        told = anomalies(before, after)
        assert "fresh: new spend, 300 cpu-ticks from nothing" in told
        assert "old: spend vanished, was 100" in told


class TestAttribution:
    def test_the_mover_owns_its_share(self):
        before = meter_of(search=1000, ads=1000)
        after = meter_of(search=1900, ads=1100)
        page = attribution(before, after)
        assert "the bill moved +50%, 2000 to 3000" in page
        assert "search: +90% of the move" in page
        assert "ads: +10% of the move" in page

    def test_a_flat_bill_says_so(self):
        before = meter_of(search=1000)
        after = meter_of(search=1000)
        assert attribution(before, after) == "the bill did not move\n"

    def test_movers_sort_by_magnitude(self):
        before = meter_of(a=1000, b=1000)
        after = meter_of(a=1100, b=1900)
        page = attribution(before, after)
        assert page.index("b:") < page.index("a:")
