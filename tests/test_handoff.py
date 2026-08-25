from __future__ import annotations

from fleet.audit import Journal
from fleet.control.finalizers import Departures
from fleet.cordonttl import CordonLeases
from fleet.handoff import handoff
from fleet.notes import Noteboard
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.queue import SchedulingQueue
from fleet.store import Store


def busy_shift() -> tuple:
    store = Store()
    store.add_node(Node(name="n3", capacity=Resources(cpu=1000, memory=1000)))
    journal = Journal()
    leases = CordonLeases(default_ttl=100)
    leases.cordon(store, journal, "n3", "meera", "disk swap Tuesday", now=10)
    notes = Noteboard()
    notes.pin("n3", "meera", "ignore the disk alerts until the swap", now=10)
    departures = Departures()
    store.add_task(Task(spec=TaskSpec(name="old-db", needs=Resources(cpu=1, memory=1))))
    departures.protect("old-db", "backup-janitor")
    departures.request_delete(store, "old-db", now=5)
    queue = SchedulingQueue()
    queue.offer("hungry", 100)
    for tick in range(30):
        queue.ready(tick)
    return leases, notes, departures, queue, journal


class TestNotes:
    def test_notes_expire_off_pages_but_stay_for_the_review(self):
        notes = Noteboard()
        notes.pin("n3", "meera", "temporary", now=0, ttl=10)
        assert notes.about("n3", now=5)
        assert notes.about("n3", now=10) == []
        assert notes.believed_at("n3", when=5)


class TestHandoff:
    def test_the_page_carries_every_section(self):
        leases, notes, departures, queue, journal = busy_shift()
        page = handoff(30, leases, notes, departures, queue, journal)
        assert "n3: meera, disk swap Tuesday, held 20" in page
        assert "ignore the disk alerts until the swap" in page
        assert "old-db: waiting 25 on backup-janitor" in page
        assert "longest: hungry, 30 passes" in page

    def test_a_quiet_shift_says_none_everywhere(self):
        page = handoff(
            0,
            CordonLeases(),
            Noteboard(),
            Departures(),
            SchedulingQueue(),
            Journal(),
        )
        assert page.count("none") >= 3
        assert "nothing" in page

    def test_the_sections_read_in_inheritance_order(self):
        leases, notes, departures, queue, journal = busy_shift()
        page = handoff(30, leases, notes, departures, queue, journal)
        order = [
            page.index("standing cordons:"),
            page.index("live notes:"),
            page.index("stuck leaving:"),
            page.index("the queue:"),
            page.index("recent decisions:"),
        ]
        assert order == sorted(order)
