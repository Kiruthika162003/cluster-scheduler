from __future__ import annotations

from fleet.deploystatus import StallWatch, Status, status_of
from fleet.objects import Resources, Task, TaskSpec
from fleet.roll.rolling import Roller, Rollout
from fleet.store import Store


def template() -> TaskSpec:
    return TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100))


def mid_rollout() -> tuple[Store, Roller, Rollout]:
    roller = Roller()
    store = Store()
    old = Rollout(name="web", replicas=3, template=template(), revision=1)
    for ordinal in range(3):
        task = Task(spec=roller._stamped(old, ordinal))
        task.bound_to(f"n{ordinal}")
        task.phase = "Running"
        store.add_task(task)
    fresh = Rollout(name="web", replicas=3, template=template(), revision=2)
    roller.step(store, fresh)
    return store, roller, fresh


class TestStatus:
    def test_the_mid_rollout_sentence_counts_all_populations(self):
        store, roller, roll = mid_rollout()
        told = status_of(store, roller, roll)
        assert told.sentence() == (
            "1 of 3 updated, 0 available, 3 old still serving"
        )

    def test_a_finished_rollout_reads_complete(self):
        told = Status(wanted=3, updated=3, updated_available=3, old_serving=0)
        assert told.done()
        assert told.sentence() == "rollout complete: 3 of 3 available"

    def test_availability_requires_running(self):
        store, roller, roll = mid_rollout()
        for task in store.tasks.values():
            if task.phase == "Pending":
                task.phase = "Running"
        told = status_of(store, roller, roll)
        assert told.updated_available == 1


class TestStallWatch:
    def steady(self) -> Status:
        return Status(wanted=3, updated=1, updated_available=0, old_serving=3)

    def test_a_moving_rollout_never_stalls(self):
        watch = StallWatch(patience=3)
        for tick, updated in enumerate([1, 2, 3]):
            told = Status(
                wanted=3, updated=updated, updated_available=updated,
                old_serving=3 - updated,
            )
            assert watch.observe(told, tick) is None

    def test_a_frozen_rollout_stalls_once_at_patience(self):
        watch = StallWatch(patience=3)
        told = None
        for tick in range(6):
            told = watch.observe(self.steady(), tick)
        assert watch.stalls == [
            "[3] rollout stalled 3 ticks at: 1 of 3 updated, 0 available, "
            "3 old still serving"
        ]
        assert told is None

    def test_a_done_rollout_never_stalls(self):
        watch = StallWatch(patience=1)
        done = Status(wanted=3, updated=3, updated_available=3, old_serving=0)
        for tick in range(4):
            assert watch.observe(done, tick) is None
