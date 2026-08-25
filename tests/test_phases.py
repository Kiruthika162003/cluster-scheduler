from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.objects import PHASES
from fleet.phases import (
    LEGAL_MOVES,
    check_history,
    may_move,
    story_of,
    terminal_phases,
)


class TestTable:
    def test_every_move_names_real_phases(self):
        for before, after in LEGAL_MOVES:
            assert before in PHASES and after in PHASES

    def test_every_move_tells_a_story(self):
        for move, story in LEGAL_MOVES.items():
            assert story and story_of(*move) == story

    def test_succeeded_and_failed_are_terminal(self):
        assert terminal_phases() == frozenset({"Succeeded", "Failed"})

    def test_the_happy_path_is_legal(self):
        assert may_move("Pending", "Bound")
        assert may_move("Bound", "Running")
        assert may_move("Running", "Succeeded")

    def test_resurrection_is_not(self):
        assert not may_move("Succeeded", "Pending")
        assert not may_move("Failed", "Running")

    def test_skipping_bound_is_not(self):
        assert not may_move("Pending", "Running")

    def test_unknown_phases_are_refused(self):
        with pytest.raises(Invalid):
            may_move("Pending", "Zombie")

    def test_an_illegal_story_is_refused(self):
        with pytest.raises(Invalid):
            story_of("Succeeded", "Running")


class TestHistories:
    def test_a_clean_life_passes(self):
        life = ["Pending", "Bound", "Running", "Succeeded"]
        assert check_history(life) is None

    def test_a_crashloop_life_passes(self):
        life = ["Pending", "Bound", "Pending", "Bound", "Running", "Failed"]
        assert check_history(life) is None

    def test_an_eviction_life_passes(self):
        life = ["Pending", "Bound", "Running", "Evicted", "Pending", "Bound"]
        assert check_history(life) is None

    def test_repeats_are_not_moves(self):
        assert check_history(["Running", "Running", "Succeeded"]) is None

    def test_the_first_illegal_step_is_named(self):
        life = ["Pending", "Bound", "Running", "Succeeded", "Pending"]
        assert check_history(life) == "Succeeded -> Pending"
