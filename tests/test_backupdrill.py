from __future__ import annotations

from fleet.backupdrill import backup_drill
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.snapshot import dump
from fleet.store import Store


def live_cluster() -> Store:
    store = Store()
    for number in range(2):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    task = Task(spec=TaskSpec(name="web-0", needs=Resources(cpu=300, memory=300)))
    task.bound_to("n0")
    store.add_task(task)
    return store


class TestBackupDrill:
    def test_a_healthy_backup_passes_behaviourally(self):
        report = backup_drill(live_cluster())
        assert report.passed()
        assert report.restored_objects == 3
        assert report.behaved

    def test_the_live_store_is_untouched_by_the_drill(self):
        store = live_cluster()
        before = dump(store)
        backup_drill(store)
        assert dump(store) == before

    def test_an_inconsistent_backup_is_named_not_scored(self):
        store = live_cluster()
        stray = Task(spec=TaskSpec(name="stray", needs=Resources(cpu=1, memory=1)))
        stray.phase = "Bound"
        store.add_task(stray)
        report = backup_drill(store)
        assert not report.passed()
        assert any(
            "restore inconsistent" in finding for finding in report.findings
        )

    def test_the_report_counts_what_came_back(self):
        report = backup_drill(live_cluster())
        assert report.took_snapshot
        assert report.restored_objects == 3
