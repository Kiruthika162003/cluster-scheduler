from __future__ import annotations

import pytest

from fleet.circuitbreaker import (
    COOLDOWN,
    FAILURE_THRESHOLD,
    PROBES_TO_CLOSE,
    WINDOW,
    Breaker,
    BreakerBoard,
)
from fleet.errors import Invalid


def tripped(now: int = 0) -> Breaker:
    breaker = Breaker(name="db")
    for count in range(FAILURE_THRESHOLD):
        breaker.call(now + count, works=False)
    return breaker


class TestTripping:
    def test_the_threshold_opens_the_breaker(self):
        breaker = tripped()
        assert breaker.state == "open"
        assert "5 failures inside 20 ticks" in breaker.transitions[0]

    def test_slow_failures_age_out_of_the_window(self):
        breaker = Breaker(name="db")
        for count in range(FAILURE_THRESHOLD):
            breaker.call(count * WINDOW, works=False)
        assert breaker.state == "closed"

    def test_open_refuses_with_its_name(self):
        breaker = tripped()
        outcome = breaker.call(10, works=True)
        assert outcome == "refused: breaker db is open"
        assert breaker.saved() == 1


class TestRecovery:
    def test_the_cooldown_admits_probes(self):
        breaker = tripped()
        assert breaker.call(4 + COOLDOWN, works=True) == "ok"
        assert breaker.state == "half-open"

    def test_enough_probes_close_it(self):
        breaker = tripped()
        for count in range(PROBES_TO_CLOSE):
            breaker.call(4 + COOLDOWN + count, works=True)
        assert breaker.state == "closed"

    def test_one_probe_failure_reopens_with_a_fresh_cooldown(self):
        breaker = tripped()
        breaker.call(4 + COOLDOWN, works=True)
        breaker.call(5 + COOLDOWN, works=False)
        assert breaker.state == "open"
        allowed, _ = breaker.allow(5 + COOLDOWN + COOLDOWN - 1)
        assert not allowed
        allowed, why = breaker.allow(5 + COOLDOWN + COOLDOWN)
        assert allowed and why == "probe"

    def test_closing_clears_the_old_sins(self):
        breaker = tripped()
        for count in range(PROBES_TO_CLOSE):
            breaker.call(4 + COOLDOWN + count, works=True)
        breaker.call(100, works=False)
        assert breaker.state == "closed"


class TestTheLedger:
    def test_saved_counts_the_waits_not_spent(self):
        breaker = tripped()
        for tick in range(5, 15):
            breaker.call(tick, works=True)
        assert breaker.saved() == 10

    def test_the_story_reads_in_order(self):
        breaker = tripped()
        breaker.call(4 + COOLDOWN, works=True)
        story = breaker.story().splitlines()
        assert story[0].startswith("db: half-open")
        assert "closed -> open" in story[1]
        assert "open -> half-open" in story[2]


class TestTheBoard:
    def test_the_board_lists_the_open(self):
        board = BreakerBoard()
        board.watch("db")
        board.watch("cache")
        for count in range(FAILURE_THRESHOLD):
            board.breakers["db"].call(count, works=False)
        assert board.open_now() == ["db"]

    def test_double_watching_is_refused(self):
        board = BreakerBoard()
        board.watch("db")
        with pytest.raises(Invalid):
            board.watch("db")
