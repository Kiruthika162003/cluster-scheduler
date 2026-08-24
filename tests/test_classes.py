from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.sched.classes import BANDS, Verdicts, class_of, number_for


class TestBands:
    def test_the_names_map_to_their_numbers(self):
        assert number_for("system") > number_for("critical") > number_for("normal")
        assert number_for("batch") > number_for("scavenger")

    def test_an_unknown_class_is_refused(self):
        with pytest.raises(Invalid):
            number_for("vip")

    def test_class_of_rounds_down_to_the_band(self):
        assert class_of(10000) == "system"
        assert class_of(1500) == "critical"
        assert class_of(101) == "normal"
        assert class_of(5) == "scavenger"

    def test_the_round_trip_holds_on_the_floors(self):
        for name, floor in BANDS.items():
            assert class_of(floor) == name


class TestMatrix:
    def test_higher_bands_displace_lower(self):
        verdicts = Verdicts()
        assert verdicts.may_displace("critical", "normal")
        assert verdicts.may_displace("normal", "batch")
        assert not verdicts.may_displace("normal", "critical")

    def test_nothing_displaces_system_but_system(self):
        verdicts = Verdicts()
        for mover in BANDS:
            expected = mover == "system"
            assert verdicts.may_displace(mover, "system") is expected

    def test_batch_may_never_displace_anything(self):
        verdicts = Verdicts()
        for victim in BANDS:
            assert not verdicts.may_displace("batch", victim)

    def test_nobody_displaces_their_own_class_except_system(self):
        verdicts = Verdicts()
        for name in BANDS:
            expected = name == "system"
            assert verdicts.may_displace(name, name) is expected

    def test_the_matrix_covers_every_pair(self):
        assert len(Verdicts().matrix()) == len(BANDS) ** 2

    def test_unknown_names_are_refused(self):
        with pytest.raises(Invalid):
            Verdicts().may_displace("vip", "normal")

    def test_the_render_reads_as_a_table(self):
        page = Verdicts().rendered()
        assert "system" in page and "yes" in page and "." in page
        assert len(page.splitlines()) == len(BANDS) + 1
