from __future__ import annotations

from fleet.deploystatus import StallWatch
from fleet.objects import Resources, Task, TaskSpec
from fleet.roll.autopause import AutoPauser
from fleet.roll.rolling import Roller, Rollout
from fleet.store import Store


def stuck_rollout() -> tuple[Store, Roller, Rollout]:
    roller = Roller()
    store = Store()
    seed = Rollout(
        name="web",
        replicas=2,
        template=TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100)),
        revision=1,
    )
    for ordinal in range(2):
        task = Task(spec=roller._stamped(seed, ordinal))
        task.bound_to(f"n{ordinal}")
        task.phase = "Running"
        store.add_task(task)
    fresh = Rollout(
        name="web",
        replicas=2,
        template=seed.template,
        revision=2,
    )
    roller.step(store, fresh)
    return store, roller, fresh


class TestAutoPause:
    def test_a_stalled_rollout_is_paused_and_paged_once(self):
        store, roller, roll = stuck_rollout()
        pauser = AutoPauser(watch=StallWatch(patience=3))
        pages = []
        for tick in range(8):
            roller.step(store, roll)
            page = pauser.observe(store, roller, roll, tick)
            if page:
                pages.append(page)
        assert len(pages) == 1
        assert "rollout paused, resume is yours" in pages[0]
        assert roller.paused

    def test_a_moving_rollout_is_left_alone(self):
        store, roller, roll = stuck_rollout()
        pauser = AutoPauser(watch=StallWatch(patience=3))
        for tick in range(6):
            for task in store.tasks.values():
                if task.phase == "Pending":
                    task.phase = "Running"
            roller.step(store, roll)
            assert pauser.observe(store, roller, roll, tick) is None
        assert not roller.paused

    def test_resume_is_a_human_verb(self):
        store, roller, roll = stuck_rollout()
        pauser = AutoPauser(watch=StallWatch(patience=2))
        for tick in range(6):
            roller.step(store, roll)
            pauser.observe(store, roller, roll, tick)
        assert roller.paused
        roller.resume()
        assert not roller.paused
        assert pauser.paused_rollouts == ["web"]
