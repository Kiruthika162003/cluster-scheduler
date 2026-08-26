from __future__ import annotations

import pytest

from fleet.bulkhead import Ship
from fleet.errors import Invalid


def rigged() -> Ship:
    ship = Ship()
    ship.partition("db", pool_size=2, queue_size=1)
    ship.partition("cache", pool_size=2, queue_size=1)
    return ship


class TestCompartments:
    def test_the_pool_runs_and_the_queue_holds(self):
        ship = rigged()
        assert ship.submit("db", "a", now=0, takes=10) == "running"
        assert ship.submit("db", "b", now=0, takes=10) == "running"
        assert ship.submit("db", "c", now=0, takes=10) == "queued"

    def test_the_full_compartment_refuses_fast(self):
        ship = rigged()
        for name in ("a", "b", "c"):
            ship.submit("db", name, now=0, takes=10)
        assert ship.submit("db", "d", now=0, takes=10) == "refused: db is full"
        assert ship.compartments["db"].refused == 1

    def test_a_stalled_db_never_touches_the_cache(self):
        ship = rigged()
        for name in ("a", "b", "c", "d"):
            ship.submit("db", name, now=0, takes=1000)
        assert ship.submit("cache", "x", now=0, takes=1) == "running"
        assert ship.drowning() == ["db"]

    def test_finishing_work_drains_the_queue(self):
        ship = rigged()
        ship.submit("db", "a", now=0, takes=5)
        ship.submit("db", "b", now=0, takes=5)
        ship.submit("db", "c", now=0, takes=5)
        ship.tick(now=5)
        compartment = ship.compartments["db"]
        assert compartment.completed == 2
        assert "c" in compartment.in_flight
        assert compartment.queued == []

    def test_unknown_dependencies_are_named(self):
        with pytest.raises(Invalid):
            rigged().submit("ghost", "a", now=0, takes=1)

    def test_a_zero_pool_is_refused(self):
        with pytest.raises(Invalid):
            Ship().partition("bad", pool_size=0, queue_size=1)


class TestTheReport:
    def test_the_water_line_shows_the_drowning(self):
        ship = rigged()
        for name in ("a", "b", "c"):
            ship.submit("db", name, now=0, takes=100)
        ship.submit("cache", "x", now=0, takes=1)
        page = ship.report()
        assert page.splitlines() == [
            "1 compartment(s) at the water line",
            "  cache: 1/2 running, 0/1 queued, 0 refused",
            "  db: 2/2 running, 1/1 queued, 0 refused",
        ]
