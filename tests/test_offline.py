from __future__ import annotations

from fleet.sched.offline import (
    NODE,
    adversarial_mix,
    floor_bins,
    friendly_mix,
    pack,
    waste,
)


class TestRules:
    def test_first_fit_takes_the_first_room(self):
        packing = pack([600, 300, 300], rule="first")
        assert packing.bins == [900, 300]

    def test_best_fit_takes_the_tightest_room(self):
        packing = pack([600, 700, 300, 400], rule="best")
        assert packing.bins == [1000, 1000]

    def test_first_fit_can_lose_to_best_fit(self):
        assert len(pack([600, 700, 300, 400], rule="first").bins) == 3

    def test_an_oversize_stream_opens_a_bin_each(self):
        packing = pack([NODE, NODE], rule="first")
        assert packing.bins == [NODE, NODE]

    def test_decreasing_sorts_before_packing(self):
        packing = pack([100, 900], rule="first", decreasing=True)
        assert packing.bins == [1000]


class TestArithmetic:
    def test_the_floor_rounds_up(self):
        assert floor_bins([500, 501]) == 2
        assert floor_bins([500, 500]) == 1

    def test_no_packer_beats_the_floor(self):
        for sizes in (friendly_mix(), adversarial_mix()):
            for rule in ("first", "best"):
                for decreasing in (False, True):
                    assert len(pack(sizes, rule, decreasing).bins) >= floor_bins(sizes)

    def test_waste_accounts_for_every_slack_slot(self):
        packing = pack([600, 300], rule="first")
        assert waste(packing) == NODE - 900

    def test_the_mixes_are_deterministic(self):
        assert friendly_mix() == friendly_mix()
        assert adversarial_mix() == adversarial_mix()
