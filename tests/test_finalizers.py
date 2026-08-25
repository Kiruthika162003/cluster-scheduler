from __future__ import annotations

import pytest

from fleet.control.finalizers import Departures
from fleet.errors import Invalid, NotFound
from fleet.objects import Resources, Task, TaskSpec
from fleet.store import Store


def store_with(name: str = "db") -> Store:
    store = Store()
    store.add_task(
        Task(spec=TaskSpec(name=name, needs=Resources(cpu=1, memory=1)))
    )
    return store


class TestPlainDeletion:
    def test_an_unprotected_object_deletes_immediately(self):
        store = store_with()
        departures = Departures()
        assert departures.request_delete(store, "db", now=0) == "deleted"
        assert "db" not in store.tasks

    def test_deleting_a_ghost_is_not_found(self):
        with pytest.raises(NotFound):
            Departures().request_delete(Store(), "ghost", now=0)


class TestProtectedDeletion:
    def test_a_protected_object_only_marks_leaving(self):
        store = store_with()
        departures = Departures()
        departures.protect("db", "disk-janitor")
        told = departures.request_delete(store, "db", now=5)
        assert told == "leaving, waiting on disk-janitor"
        assert "db" in store.tasks

    def test_the_last_signature_completes_the_delete(self):
        store = store_with()
        departures = Departures()
        departures.protect("db", "disk-janitor")
        departures.protect("db", "dns-janitor")
        departures.request_delete(store, "db", now=5)
        assert departures.clear(store, "db", "dns-janitor") == "cleared dns-janitor"
        assert "db" in store.tasks
        assert departures.clear(store, "db", "disk-janitor") == "deleted"
        assert "db" not in store.tasks
        assert departures.completed == 1

    def test_clearing_before_the_delete_just_clears(self):
        store = store_with()
        departures = Departures()
        departures.protect("db", "disk-janitor")
        departures.clear(store, "db", "disk-janitor")
        assert departures.request_delete(store, "db", now=0) == "deleted"

    def test_an_unheld_signature_is_refused(self):
        store = store_with()
        departures = Departures()
        with pytest.raises(Invalid):
            departures.clear(store, "db", "impostor")

    def test_protecting_a_leaving_object_is_refused(self):
        store = store_with()
        departures = Departures()
        departures.protect("db", "disk-janitor")
        departures.request_delete(store, "db", now=0)
        with pytest.raises(Invalid):
            departures.protect("db", "late-janitor")


class TestStuck:
    def test_stuck_names_the_janitor_and_the_wait(self):
        store = store_with()
        departures = Departures()
        departures.protect("db", "disk-janitor")
        departures.request_delete(store, "db", now=10)
        assert departures.stuck(now=25, patience=10) == [
            "db: waiting 15 on disk-janitor"
        ]

    def test_a_fresh_departure_is_not_stuck_yet(self):
        store = store_with()
        departures = Departures()
        departures.protect("db", "disk-janitor")
        departures.request_delete(store, "db", now=10)
        assert departures.stuck(now=15, patience=10) == []
