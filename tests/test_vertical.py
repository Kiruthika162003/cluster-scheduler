from __future__ import annotations

from fleet.vertical import FightMeter, Sizer, reclaim


class TestSizer:
    def test_a_short_window_proposes_no_change(self):
        sizer = Sizer(window=5)
        for used in (100, 110, 90):
            sizer.observe("t", used)
        assert sizer.propose("t", current_request=500) == 500

    def test_a_full_window_sizes_from_the_peak(self):
        sizer = Sizer(window=3)
        for used in (100, 140, 120):
            sizer.observe("t", used)
        assert sizer.propose("t", current_request=500) == 168

    def test_the_window_slides(self):
        sizer = Sizer(window=2)
        for used in (900, 100, 100):
            sizer.observe("t", used)
        assert sizer.propose("t", current_request=500) == 120

    def test_reclaim_never_goes_negative(self):
        assert reclaim(500, 168) == 332
        assert reclaim(100, 168) == 0


class TestFightMeter:
    def test_equilibrium_makes_no_moves(self):
        meter = FightMeter(request=500, replicas=4, total_load=1400.0)
        assert meter.rounds(10, "off") == 0

    def test_overload_adds_replicas(self):
        meter = FightMeter(request=100, replicas=1, total_load=90.0)
        meter.rounds(1, "off")
        assert meter.replicas == 2

    def test_deep_idle_sheds_replicas(self):
        meter = FightMeter(request=1000, replicas=4, total_load=400.0)
        meter.rounds(1, "off")
        assert meter.replicas == 3

    def test_private_constants_never_settle(self):
        meter = FightMeter(request=500, replicas=4, total_load=1400.0)
        first = meter.rounds(10, "private")
        second = meter.rounds(10, "private") - first
        assert second > 0

    def test_the_truce_settles_and_stays(self):
        meter = FightMeter(request=2000, replicas=4, total_load=1400.0)
        meter.rounds(5, "truce")
        assert meter.moves == ["request 2000->500"]
