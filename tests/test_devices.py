from __future__ import annotations

import pytest

from fleet.errors import Conflict, Invalid, NotFound
from fleet.sched.devices import DeviceNode, DevicePool


def pool() -> DevicePool:
    built = DevicePool()
    built.add_node(
        DeviceNode(name="big8", slots=8, linked_pairs=((0, 1), (2, 3)))
    )
    built.add_node(DeviceNode(name="mid4", slots=4, linked_pairs=((0, 1),)))
    built.add_node(DeviceNode(name="tiny2", slots=2))
    return built


class TestPlacement:
    def test_the_small_job_avoids_the_empty_eight_box(self):
        devices = pool()
        assert devices.place("small", count=2) == "tiny2"
        assert devices.stranded_on_empty_boxes() == 8

    def test_fewest_but_sufficient_wins(self):
        devices = pool()
        devices.place("first", count=2)
        assert devices.place("second", count=3) == "mid4"

    def test_the_eight_slot_job_finds_its_box(self):
        devices = pool()
        devices.place("small", count=2)
        assert devices.place("training", count=8) == "big8"

    def test_a_linked_pair_needs_real_wiring(self):
        devices = pool()
        node = devices.place("paired", count=2, linked=True)
        assert node in ("mid4", "big8")
        assert devices.placements["paired"][1] in ((0, 1), (2, 3))

    def test_linked_means_exactly_two(self):
        with pytest.raises(Invalid):
            pool().place("odd", count=3, linked=True)

    def test_no_room_is_a_named_refusal(self):
        devices = pool()
        with pytest.raises(NotFound):
            devices.place("huge", count=9)

    def test_double_placement_is_refused(self):
        devices = pool()
        devices.place("job", count=1)
        with pytest.raises(Conflict):
            devices.place("job", count=1)


class TestSlices:
    def test_slices_pack_onto_one_partitioned_device(self):
        devices = pool()
        slot_a = devices.place_slice("infer-a", "mid4", share=4)
        slot_b = devices.place_slice("infer-b", "mid4", share=4)
        assert slot_a == slot_b

    def test_a_full_partition_opens_the_next_device(self):
        devices = pool()
        for number in range(2):
            devices.place_slice(f"half-{number}", "tiny2", share=2)
        slot = devices.place_slice("half-2", "tiny2", share=2)
        assert slot == 1

    def test_odd_shares_are_refused(self):
        with pytest.raises(Invalid):
            pool().place_slice("weird", "tiny2", share=3)

    def test_sliced_slots_are_not_whole_slots(self):
        devices = pool()
        devices.place_slice("half", "tiny2", share=2)
        devices.place("whole", count=1)
        node, slots = devices.placements["whole"]
        assert (node, slots) != ("tiny2", (0,))


class TestRelease:
    def test_release_returns_the_slots(self):
        devices = pool()
        devices.place("job", count=2)
        devices.release("job")
        assert devices.place("job2", count=2) == "tiny2"

    def test_the_last_slice_unpartitions_the_device(self):
        devices = pool()
        devices.place_slice("half", "tiny2", share=2)
        devices.release("half")
        assert devices.nodes["tiny2"].slices == {}

    def test_releasing_nothing_is_named(self):
        with pytest.raises(NotFound):
            pool().release("ghost")

    def test_the_report_reads_free_and_partitioned(self):
        devices = pool()
        devices.place("job", count=1)
        devices.place_slice("half", "big8", share=2)
        page = devices.report()
        assert "big8: 7/8 free, 1 partitioned" in page
        assert "tiny2: 1/2 free" in page
