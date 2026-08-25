from __future__ import annotations

from fleet.alerts import Event, Pager
from fleet.audit import Journal
from fleet.faultreview import review
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def lived_incident() -> tuple[Store, Journal, Pager, int]:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    cursor = len(store.events)
    task = Task(spec=TaskSpec(name="web-0", needs=Resources(cpu=100, memory=100)))
    task.bound_to("n0")
    task.phase = "Running"
    store.add_task(task)
    journal = Journal()
    journal.note(10, "monitor", "n0", "mark-not-ready", "silent 4 ticks")
    journal.note(20, "engine", "web-0", "bind", "n0 recovered")
    journal.note(90, "someone", "later", "noise", "outside the window")
    pager = Pager()
    for tick in (10, 11, 12):
        pager.take(Event(tick=tick, subject="n0", state="down"))
    return store, journal, pager, cursor


class TestReview:
    def test_the_sections_arrive_in_reading_order(self):
        store, journal, pager, cursor = lived_incident()
        page = review(store, journal, pager, 0, 60, cursor)
        order = [
            page.index("what changed:"),
            page.index("who did what:"),
            page.index("what it cost the pager:"),
            page.index("is the cluster whole:"),
        ]
        assert order == sorted(order)

    def test_only_window_decisions_appear(self):
        store, journal, pager, cursor = lived_incident()
        page = review(store, journal, pager, 0, 60, cursor)
        assert "mark-not-ready" in page
        assert "outside the window" not in page

    def test_the_pager_budget_is_stated(self):
        store, journal, pager, cursor = lived_incident()
        page = review(store, journal, pager, 0, 60, cursor)
        assert "1 pages delivered, 2 folded" in page

    def test_a_whole_cluster_says_yes(self):
        store, journal, pager, cursor = lived_incident()
        page = review(store, journal, pager, 0, 60, cursor)
        assert "yes; every invariant holds" in page

    def test_a_broken_cluster_leads_with_no(self):
        store, journal, pager, cursor = lived_incident()
        stray = Task(spec=TaskSpec(name="stray", needs=Resources(cpu=1, memory=1)))
        stray.phase = "Bound"
        store.add_task(stray)
        page = review(store, journal, pager, 0, 60, cursor)
        assert "NO: stray is Bound with no node" in page

    def test_a_long_decision_list_is_capped_with_a_count(self):
        store, journal, pager, cursor = lived_incident()
        for tick in range(30, 50):
            journal.note(tick, "engine", f"t{tick}", "bench", "no fit")
        page = review(store, journal, pager, 0, 60, cursor)
        assert "and 10 more decisions" in page
