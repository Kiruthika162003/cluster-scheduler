from __future__ import annotations

from fleet.flapdamp import CEILING, Dampener


class TestPenalties:
    def test_one_flap_is_forgiven_and_never_suppressed(self):
        dampener = Dampener(half_life=10)
        dampener.note_flap("web-0", now=0)
        assert dampener.in_rotation("web-0", now=0)
        assert dampener.penalty_of("web-0", now=20) == 25.0

    def test_a_burst_crosses_the_ceiling(self):
        dampener = Dampener(half_life=10)
        for now in (0, 1, 2):
            dampener.note_flap("web-0", now)
        assert not dampener.in_rotation("web-0", now=2)
        assert dampener.suppressions == 1

    def test_decay_halves_per_half_life(self):
        dampener = Dampener(half_life=10)
        dampener.note_flap("web-0", now=0)
        assert dampener.penalty_of("web-0", now=10) == 50.0
        assert dampener.penalty_of("web-0", now=30) == 12.5


class TestSuppression:
    def suppressed_endpoint(self) -> Dampener:
        dampener = Dampener(half_life=10)
        for now in (0, 1, 2):
            dampener.note_flap("web-0", now)
        return dampener

    def test_suppression_lifts_when_decay_reaches_the_floor(self):
        dampener = self.suppressed_endpoint()
        assert not dampener.in_rotation("web-0", now=10)
        assert dampener.in_rotation("web-0", now=22)

    def test_a_flap_during_suppression_extends_it(self):
        dampener = self.suppressed_endpoint()
        dampener.note_flap("web-0", now=12)
        assert not dampener.in_rotation("web-0", now=25)

    def test_no_life_sentences(self):
        dampener = self.suppressed_endpoint()
        assert dampener.in_rotation("web-0", now=200)

    def test_steady_endpoints_are_never_touched(self):
        dampener = self.suppressed_endpoint()
        assert dampener.in_rotation("web-1", now=0)
        assert dampener.penalty_of("web-1", now=0) == 0.0

    def test_the_ceiling_is_a_real_number(self):
        assert CEILING > 0
