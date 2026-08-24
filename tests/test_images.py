from __future__ import annotations

import pytest

from fleet.errors import NotFound
from fleet.images import PullLog, Registry, rollout_by_digest, rollout_by_tag


def registry() -> Registry:
    made = Registry()
    made.push("web:latest", "sha-aaa")
    return made


class TestRegistry:
    def test_resolve_returns_the_current_digest(self):
        assert registry().resolve("web:latest") == "sha-aaa"

    def test_an_unknown_tag_is_not_found(self):
        with pytest.raises(NotFound):
            registry().resolve("ghost:latest")

    def test_a_push_moves_the_tag(self):
        held = registry()
        held.push("web:latest", "sha-bbb")
        assert held.resolve("web:latest") == "sha-bbb"


class TestRollouts:
    def test_a_tag_rollout_splits_when_the_tag_moves(self):
        builds = rollout_by_tag(
            registry(), PullLog(), "web:latest", replicas=6, move_at=3,
            new_digest="sha-bbb",
        )
        assert builds == {"sha-aaa", "sha-bbb"}

    def test_the_split_lands_exactly_at_the_move(self):
        log = PullLog()
        rollout_by_tag(
            registry(), log, "web:latest", replicas=6, move_at=3,
            new_digest="sha-bbb",
        )
        assert log.ran["web-2"] == "sha-aaa"
        assert log.ran["web-3"] == "sha-bbb"

    def test_a_digest_rollout_is_one_build_by_construction(self):
        builds = rollout_by_digest(
            registry(), PullLog(), "web:latest", replicas=6, move_at=3,
            new_digest="sha-bbb",
        )
        assert builds == {"sha-aaa"}

    def test_the_tag_still_moved_underneath(self):
        held = registry()
        rollout_by_digest(
            held, PullLog(), "web:latest", replicas=6, move_at=3,
            new_digest="sha-bbb",
        )
        assert held.resolve("web:latest") == "sha-bbb"

    def test_a_quiet_tag_gives_one_build_either_way(self):
        by_tag = rollout_by_tag(
            registry(), PullLog(), "web:latest", replicas=4, move_at=99,
            new_digest="sha-bbb",
        )
        by_digest = rollout_by_digest(
            registry(), PullLog(), "web:latest", replicas=4, move_at=99,
            new_digest="sha-bbb",
        )
        assert by_tag == by_digest == {"sha-aaa"}
