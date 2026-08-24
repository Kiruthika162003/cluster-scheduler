from __future__ import annotations

from fleet.sched.queue import BACKOFF_CAP, SchedulingQueue


class TestOrdering:
    def test_ready_is_priority_then_name(self):
        queue = SchedulingQueue()
        queue.offer("late", 1)
        queue.offer("urgent", 9)
        queue.offer("early", 1)
        assert queue.ready(now=0) == ["urgent", "early", "late"]

    def test_a_reoffer_does_not_reset_state(self):
        queue = SchedulingQueue()
        queue.offer("t", 1)
        queue.refuse("t", now=0)
        queue.offer("t", 1)
        assert queue.waiting["t"].refusals == 1

    def test_forget_removes_the_entry(self):
        queue = SchedulingQueue()
        queue.offer("t", 1)
        queue.forget("t")
        assert queue.ready(now=0) == []


class TestBackoff:
    def test_each_refusal_doubles_the_bench(self):
        queue = SchedulingQueue()
        queue.offer("t", 1)
        assert queue.refuse("t", now=0) == 2
        assert queue.refuse("t", now=0) == 4
        assert queue.refuse("t", now=0) == 8

    def test_the_bench_caps(self):
        queue = SchedulingQueue()
        queue.offer("t", 1)
        for _ in range(10):
            wait = queue.refuse("t", now=0)
        assert wait == BACKOFF_CAP

    def test_a_benched_task_is_not_ready(self):
        queue = SchedulingQueue()
        queue.offer("t", 1)
        queue.refuse("t", now=0)
        assert queue.ready(now=1) == []
        assert queue.ready(now=2) == ["t"]


class TestShapeChange:
    def test_a_new_node_clears_every_bench(self):
        queue = SchedulingQueue()
        for name in ("a", "b"):
            queue.offer(name, 1)
            queue.refuse(name, now=0)
        assert queue.shape_changed(now=0) == 2
        assert queue.ready(now=0) == ["a", "b"]

    def test_unbenched_tasks_are_not_double_promoted(self):
        queue = SchedulingQueue()
        queue.offer("free", 1)
        assert queue.shape_changed(now=0) == 0


class TestStarvation:
    def test_waited_passes_accumulate(self):
        queue = SchedulingQueue()
        queue.offer("t", 1)
        for now in range(5):
            queue.ready(now)
        assert queue.starving(passes=5) == ["t"]
        assert queue.starving(passes=6) == []

    def test_scheduled_tasks_never_starve(self):
        queue = SchedulingQueue()
        queue.offer("t", 1)
        queue.ready(now=0)
        queue.forget("t")
        assert queue.starving(passes=1) == []
