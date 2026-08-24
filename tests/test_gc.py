from __future__ import annotations

from fleet.control.gc import Collector
from fleet.objects import Resources, Task, TaskSpec
from fleet.store import Store


def finished(name: str, phase: str) -> Task:
    task = Task(spec=TaskSpec(name=name, needs=Resources(cpu=1, memory=1)))
    task.phase = phase
    return task


class TestCollector:
    def test_active_tasks_are_never_touched(self):
        store = Store()
        live = Task(spec=TaskSpec(name="live", needs=Resources(cpu=1, memory=1)))
        live.bound_to("n0")
        store.add_task(live)
        collector = Collector(ttl=0)
        assert collector.sweep(store, now=100) == 0
        assert "live" in store.tasks

    def test_ttl_removes_the_old(self):
        store = Store()
        store.add_task(finished("old", "Succeeded"))
        collector = Collector(ttl=10)
        collector.sweep(store, now=0)
        assert collector.sweep(store, now=10) == 1
        assert "old" not in store.tasks

    def test_young_finishers_survive_the_ttl(self):
        store = Store()
        store.add_task(finished("young", "Succeeded"))
        collector = Collector(ttl=10)
        collector.sweep(store, now=0)
        assert collector.sweep(store, now=9) == 0

    def test_the_cap_removes_oldest_first(self):
        store = Store()
        collector = Collector(keep_succeeded=2, ttl=10**6)
        for number in range(4):
            store.add_task(finished(f"s{number}", "Succeeded"))
            collector.sweep(store, now=number)
        assert sorted(store.tasks) == ["s2", "s3"]

    def test_the_caps_are_per_kind(self):
        store = Store()
        collector = Collector(keep_succeeded=1, keep_failed=3, ttl=10**6)
        for number in range(3):
            store.add_task(finished(f"s{number}", "Succeeded"))
            store.add_task(finished(f"f{number}", "Failed"))
            collector.sweep(store, now=number)
        names = sorted(store.tasks)
        assert names == ["f0", "f1", "f2", "s2"]

    def test_collected_accumulates(self):
        store = Store()
        collector = Collector(keep_succeeded=0, ttl=10**6)
        store.add_task(finished("a", "Succeeded"))
        collector.sweep(store, now=0)
        store.add_task(finished("b", "Succeeded"))
        collector.sweep(store, now=1)
        assert collector.collected == 2

    def test_externally_deleted_tasks_are_forgotten(self):
        store = Store()
        store.add_task(finished("gone", "Succeeded"))
        collector = Collector()
        collector.sweep(store, now=0)
        store.remove_task("gone")
        collector.sweep(store, now=1)
        assert "gone" not in collector.finished_at
