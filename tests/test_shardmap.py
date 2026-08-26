from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.shardmap import Ring, modulo_assignment, moved_keys

KEYS = [f"key-{number}" for number in range(2000)]


def five_nodes(points: int = 64) -> Ring:
    ring = Ring(points_per_node=points)
    for number in range(5):
        ring.add(f"n{number}")
    return ring


class TestTheRing:
    def test_ownership_is_deterministic(self):
        ring = five_nodes()
        assert ring.owner("key-7") == ring.owner("key-7")

    def test_every_key_finds_an_owner(self):
        ring = five_nodes()
        owners = set(ring.assignment(KEYS).values())
        assert owners == {f"n{number}" for number in range(5)}

    def test_an_empty_ring_is_refused(self):
        with pytest.raises(Invalid):
            Ring().owner("key")

    def test_double_adding_is_refused(self):
        ring = five_nodes()
        with pytest.raises(Invalid):
            ring.add("n0")

    def test_removing_the_absent_is_refused(self):
        with pytest.raises(Invalid):
            five_nodes().remove("ghost")


class TestTopologyChanges:
    def test_adding_a_node_moves_about_a_sixth(self):
        ring = five_nodes()
        before = ring.assignment(KEYS)
        ring.add("n5")
        moved, share = moved_keys(before, ring.assignment(KEYS))
        assert moved == 269
        assert share == 0.1345

    def test_modulo_hashing_moves_five_sixths(self):
        _, share = moved_keys(
            modulo_assignment(KEYS, 5), modulo_assignment(KEYS, 6)
        )
        assert share == 0.8335

    def test_removal_spills_only_the_dead_nodes_arcs(self):
        ring = five_nodes()
        before = ring.assignment(KEYS)
        ring.remove("n2")
        after = ring.assignment(KEYS)
        for key in KEYS:
            if before[key] != "n2":
                assert after[key] == before[key]

    def test_mismatched_key_sets_are_refused(self):
        with pytest.raises(Invalid):
            moved_keys({"a": "n0"}, {"b": "n0"})

    def test_empty_maps_move_nothing(self):
        assert moved_keys({}, {}) == (0, 0.0)


class TestBalance:
    def test_virtual_points_narrow_the_lumps(self):
        lumpy = five_nodes(points=1).balance(KEYS)
        smooth = five_nodes(points=64).balance(KEYS)
        assert lumpy == 1.64
        assert smooth == 1.18
        assert smooth < lumpy

    def test_balance_without_keys_is_refused(self):
        with pytest.raises(Invalid):
            five_nodes().balance([])
