from __future__ import annotations

import pytest

from fleet.errors import Conflict, Invalid
from fleet.idempotency import KEY_TTL, KeyStore


class TestTheHappyPath:
    def test_a_fresh_key_runs(self):
        store = KeyStore()
        assert store.begin("scale-web-1", now=0) == "run"

    def test_a_finished_key_replays_its_response(self):
        store = KeyStore()
        store.begin("scale-web-1", now=0)
        store.finish("scale-web-1", response="scaled to 5", now=3)
        assert store.begin("scale-web-1", now=10) == "replay: scaled to 5"
        assert store.replays_served == 1

    def test_an_empty_key_is_refused(self):
        with pytest.raises(Invalid):
            KeyStore().begin("", now=0)


class TestTheDangerousWindow:
    def test_a_replay_mid_flight_waits(self):
        store = KeyStore()
        store.begin("scale-web-1", now=0)
        outcome = store.begin("scale-web-1", now=1)
        assert outcome == "wait: the first attempt is still running"
        assert store.duplicates_prevented == 1

    def test_finishing_twice_is_refused(self):
        store = KeyStore()
        store.begin("k", now=0)
        store.finish("k", response="done", now=1)
        with pytest.raises(Conflict):
            store.finish("k", response="done again", now=2)

    def test_finishing_the_unbegun_is_refused(self):
        with pytest.raises(Invalid):
            KeyStore().finish("ghost", response="x", now=0)

    def test_a_crashed_attempt_releases_the_key(self):
        store = KeyStore()
        store.begin("k", now=0)
        store.abandon("k")
        assert store.begin("k", now=5) == "run"

    def test_abandoning_the_finished_is_refused(self):
        store = KeyStore()
        store.begin("k", now=0)
        store.finish("k", response="done", now=1)
        with pytest.raises(Invalid):
            store.abandon("k")


class TestTheHorizon:
    def test_an_expired_key_runs_fresh(self):
        store = KeyStore()
        store.begin("k", now=0)
        store.finish("k", response="done", now=1)
        assert store.begin("k", now=1 + KEY_TTL) == "run"

    def test_inside_the_horizon_the_replay_holds(self):
        store = KeyStore()
        store.begin("k", now=0)
        store.finish("k", response="done", now=1)
        assert store.begin("k", now=KEY_TTL) == "replay: done"

    def test_the_meter_counts_both_saves(self):
        store = KeyStore()
        store.begin("k", now=0)
        store.begin("k", now=1)
        store.finish("k", response="done", now=2)
        store.begin("k", now=3)
        assert store.meter() == "1 replays served, 1 duplicates prevented"
