from __future__ import annotations

from fleet.audit import Journal
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.report import cluster_report, node_table, phase_table
from fleet.store import Store


class TestJournal:
    def busy(self) -> Journal:
        journal = Journal()
        journal.note(1, "scheduler", "web-0", "bind", "n0 scored highest")
        journal.note(2, "monitor", "n1", "mark-not-ready", "silent 4 ticks")
        journal.note(3, "scheduler", "web-1", "refuse", "no node fits 5000m")
        return journal

    def test_about_filters_by_subject(self):
        journal = self.busy()
        assert [d.verb for d in journal.about("web-0")] == ["bind"]

    def test_by_filters_by_actor_most_recent(self):
        journal = self.busy()
        assert [d.subject for d in journal.by("scheduler")] == ["web-0", "web-1"]

    def test_the_story_reads_in_order(self):
        journal = self.busy()
        assert "bind web-0" in journal.story("web-0")

    def test_an_unknown_subject_says_so(self):
        assert "nothing recorded" in Journal().story("ghost")

    def test_the_journal_is_capped(self):
        journal = Journal(keep=2)
        for tick in range(5):
            journal.note(tick, "a", f"s{tick}", "v", "r")
        assert [d.tick for d in journal.decisions] == [3, 4]

    def test_testimony_outlives_the_object(self):
        journal = self.busy()
        assert journal.about("n1")


class TestReport:
    def small_cluster(self) -> Store:
        store = Store()
        store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
        task = Task(spec=TaskSpec(name="t0", needs=Resources(cpu=300, memory=200)))
        task.bound_to("n0")
        store.add_task(task)
        store.add_task(Task(spec=TaskSpec(name="t1", needs=Resources(cpu=1, memory=1))))
        return store

    def test_the_node_table_shows_load(self):
        table = node_table(self.small_cluster())
        assert "n0" in table and "300/1000" in table

    def test_the_phase_table_counts(self):
        table = phase_table(self.small_cluster())
        assert "Bound      1" in table and "Pending    1" in table

    def test_the_report_heads_with_totals(self):
        report = cluster_report(self.small_cluster())
        assert report.startswith("nodes 1, tasks 2, cpu 300/1000")
