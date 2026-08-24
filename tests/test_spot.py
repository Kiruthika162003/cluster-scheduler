from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.spot import Notice, SpotMarket, WorkTracker, evacuate, reclaim
from fleet.store import Store


def spotted_store() -> Store:
    store = Store()
    store.add_node(Node(name="spot-0", capacity=Resources(cpu=1000, memory=1000)))
    store.add_node(Node(name="stable", capacity=Resources(cpu=1000, memory=1000)))
    task = Task(spec=TaskSpec(name="job", needs=Resources(cpu=100, memory=100)))
    task.bound_to("spot-0")
    task.phase = "Running"
    store.add_task(task)
    return store


class TestMarket:
    def test_the_notice_precedes_the_reclaim_by_the_window(self):
        market = SpotMarket(reclaims={"spot-0": 10}, notice_window=4)
        assert market.tick(5) == []
        notices = market.tick(6)
        assert notices == [Notice(node="spot-0", issued_at=6, deadline=10)]

    def test_the_reclaim_lands_on_schedule(self):
        market = SpotMarket(reclaims={"spot-0": 10})
        assert market.reclaimed_now(9) == []
        assert market.reclaimed_now(10) == ["spot-0"]

    def test_notices_are_remembered(self):
        market = SpotMarket(reclaims={"spot-0": 10}, notice_window=4)
        market.tick(6)
        assert len(market.notices) == 1


class TestTracker:
    def test_progress_accumulates_and_finishes(self):
        store = spotted_store()
        tracker = WorkTracker(needed={"job": 2})
        tracker.advance(store)
        assert tracker.progress["job"] == 1
        tracker.advance(store)
        assert store.get_task("job").phase == "Succeeded"
        assert tracker.finished == ["job"]

    def test_a_loss_pays_the_progress_again(self):
        store = spotted_store()
        tracker = WorkTracker(needed={"job": 10})
        tracker.advance(store)
        tracker.advance(store)
        tracker.lose(store.get_task("job"))
        assert tracker.lost_ticks == 2 and tracker.reruns == 1
        assert tracker.progress["job"] == 0

    def test_losing_an_unstarted_task_is_free(self):
        store = spotted_store()
        tracker = WorkTracker(needed={"job": 10})
        tracker.lose(store.get_task("job"))
        assert tracker.lost_ticks == 0 and tracker.reruns == 0


class TestEvacuateAndReclaim:
    def test_evacuate_moves_without_losing(self):
        store = spotted_store()
        moved = evacuate(store, "spot-0")
        assert moved == 1
        assert store.get_task("job").phase == "Pending"

    def test_reclaim_loses_the_stragglers_and_the_node(self):
        store = spotted_store()
        tracker = WorkTracker(needed={"job": 10})
        tracker.advance(store)
        lost = reclaim(store, tracker, "spot-0")
        assert lost == 1
        assert tracker.lost_ticks == 1
        assert "spot-0" not in store.nodes
        assert store.get_task("job").restarts == 1

    def test_reclaiming_an_evacuated_node_loses_nothing(self):
        store = spotted_store()
        tracker = WorkTracker(needed={"job": 10})
        evacuate(store, "spot-0")
        lost = reclaim(store, tracker, "spot-0")
        assert lost == 0 and tracker.lost_ticks == 0
