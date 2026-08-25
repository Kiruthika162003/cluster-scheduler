from __future__ import annotations

from fleet.queuestats import BAND_NAMES, snapshot
from fleet.sched.queue import SchedulingQueue


def worn_queue() -> SchedulingQueue:
    queue = SchedulingQueue()
    for name, waited in (("fresh", 0), ("brief", 3), ("older", 10), ("stuck", 40)):
        queue.offer(name, 100)
        queue.waiting[name].passes_waited = waited
    return queue


class TestSnapshot:
    def test_the_bands_partition_the_queue(self):
        stats = snapshot(worn_queue())
        assert stats.counts == (1, 1, 1, 1)
        assert stats.waiting_total == 4

    def test_the_longest_waiter_is_named(self):
        stats = snapshot(worn_queue())
        assert stats.longest_name == "stuck"
        assert stats.longest_waited == 40

    def test_an_empty_queue_renders_calmly(self):
        stats = snapshot(SchedulingQueue())
        assert stats.waiting_total == 0
        assert stats.longest_name is None
        assert "0 waiting" in stats.render()

    def test_the_render_lists_every_band(self):
        page = snapshot(worn_queue()).render()
        for name in BAND_NAMES:
            assert name in page
        assert "longest: stuck, 40 passes" in page

    def test_the_mean_would_have_hidden_the_tail(self):
        queue = worn_queue()
        waits = [held.passes_waited for held in queue.waiting.values()]
        mean = sum(waits) / len(waits)
        stats = snapshot(queue)
        assert mean < 15
        assert stats.longest_waited == 40
