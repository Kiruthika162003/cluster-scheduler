from __future__ import annotations

from fleet.audit import Journal
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.oncall import brief
from fleet.store import Store


def quiet_cluster() -> tuple[Store, Journal, int]:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    task = Task(spec=TaskSpec(name="web-0", needs=Resources(cpu=100, memory=100)))
    task.bound_to("n0")
    task.phase = "Running"
    store.add_task(task)
    journal = Journal()
    journal.note(1, "scheduler", "web-0", "bind", "n0 accepted")
    return store, journal, len(store.events)


class TestBrief:
    def test_a_quiet_brief_says_quiet_in_every_section(self):
        store, journal, cursor = quiet_cluster()
        page = brief(store, journal, since=cursor, running=1, serving=1)
        assert "nothing; invariants hold" in page
        assert "nothing changed" in page
        assert "1 running, 1 serving" in page
        assert "conformance checks hold" in page

    def test_the_sections_arrive_in_triage_order(self):
        store, journal, cursor = quiet_cluster()
        page = brief(store, journal, since=cursor, running=1, serving=1)
        order = [
            page.index("broken:"),
            page.index("changed:"),
            page.index("doing:"),
            page.index("recent decisions:"),
            page.index("promises:"),
        ]
        assert order == sorted(order)

    def test_a_ghost_gap_is_called_out(self):
        store, journal, cursor = quiet_cluster()
        page = brief(store, journal, since=cursor, running=5, serving=3)
        assert "2 running on nodes that cannot serve them" in page

    def test_broken_invariants_lead_the_page(self):
        store, journal, cursor = quiet_cluster()
        stray = Task(spec=TaskSpec(name="stray", needs=Resources(cpu=1, memory=1)))
        stray.phase = "Bound"
        store.add_task(stray)
        page = brief(store, journal, since=cursor, running=1, serving=1)
        assert "stray is Bound with no node" in page

    def test_recent_decisions_show_the_last_lines(self):
        store, journal, cursor = quiet_cluster()
        for tick in range(2, 12):
            journal.note(tick, "engine", f"t{tick}", "bench", "no fit")
        page = brief(store, journal, since=cursor, running=1, serving=1)
        assert "t11" in page and "t6" not in page
