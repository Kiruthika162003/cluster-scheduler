from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.gracefulshutdown import LAME_DUCK_TICKS, Shutdown


class TestServing:
    def test_a_serving_process_takes_work(self):
        shutdown = Shutdown(drain_deadline=20)
        assert shutdown.accept("r1", now=0, takes=5)
        assert shutdown.ready()

    def test_a_theatrical_deadline_is_refused(self):
        with pytest.raises(Invalid, match="theatre"):
            Shutdown(drain_deadline=LAME_DUCK_TICKS)


class TestTheLameDuck:
    def test_the_duck_refuses_new_work_but_serves_the_old(self):
        shutdown = Shutdown(drain_deadline=20)
        shutdown.accept("old", now=0, takes=10)
        shutdown.begin(now=1)
        assert not shutdown.ready()
        assert not shutdown.accept("new", now=2, takes=1)
        assert shutdown.refused == 1
        assert "old" in shutdown.in_flight

    def test_the_duck_lasts_its_full_act(self):
        shutdown = Shutdown(drain_deadline=20)
        shutdown.begin(now=0)
        assert shutdown.tick(now=LAME_DUCK_TICKS - 1) == "lame-duck"

    def test_beginning_twice_is_refused(self):
        shutdown = Shutdown(drain_deadline=20)
        shutdown.begin(now=0)
        with pytest.raises(Invalid):
            shutdown.begin(now=1)


class TestDraining:
    def test_an_empty_drain_closes_clean(self):
        shutdown = Shutdown(drain_deadline=20)
        shutdown.begin(now=0)
        assert shutdown.tick(now=LAME_DUCK_TICKS) == "closed clean"
        assert shutdown.epitaph().startswith("graceful")

    def test_work_that_finishes_in_time_is_graceful(self):
        shutdown = Shutdown(drain_deadline=20)
        shutdown.accept("r1", now=0, takes=10)
        shutdown.begin(now=1)
        assert shutdown.tick(now=6) == "draining"
        assert shutdown.tick(now=11) == "closed clean"
        assert shutdown.finished == 1

    def test_the_deadline_cuts_the_stuck(self):
        shutdown = Shutdown(drain_deadline=15)
        shutdown.accept("stuck", now=0, takes=1000)
        shutdown.accept("quick", now=0, takes=3)
        shutdown.begin(now=1)
        outcome = shutdown.tick(now=16)
        assert outcome == "closed hard: cut 1"
        assert shutdown.cut == ["stuck"]
        assert shutdown.finished == 1

    def test_the_epitaph_refutes_the_claim(self):
        shutdown = Shutdown(drain_deadline=15)
        shutdown.accept("stuck", now=0, takes=1000)
        shutdown.begin(now=0)
        shutdown.tick(now=15)
        assert shutdown.epitaph() == (
            "NOT graceful: 0 finished, 0 refused during the duck, "
            "1 cut at the deadline"
        )
