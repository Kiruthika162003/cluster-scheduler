from __future__ import annotations

import pytest

from fleet.errors import NotFound
from fleet.objects import Resources, Task, TaskSpec
from fleet.roll.history import History
from fleet.roll.rolling import Roller
from fleet.store import Store


def template(tag: str) -> TaskSpec:
    return TaskSpec(
        name="tpl", needs=Resources(cpu=100, memory=100), labels=(("build", tag),)
    )


class TestHistory:
    def test_revisions_count_up(self):
        history = History(name="web")
        assert history.record(template("one")) == 1
        assert history.record(template("two")) == 2

    def test_current_is_the_latest(self):
        history = History(name="web")
        history.record(template("one"))
        history.record(template("two"))
        assert history.current().template.label_map()["build"] == "two"

    def test_an_empty_history_has_no_current(self):
        with pytest.raises(NotFound):
            History(name="web").current()

    def test_the_cap_drops_the_oldest(self):
        history = History(name="web", keep=2)
        for tag in ("one", "two", "three"):
            history.record(template(tag))
        assert [entry.revision for entry in history.entries] == [2, 3]

    def test_find_of_a_dropped_revision_fails(self):
        history = History(name="web", keep=1)
        history.record(template("one"))
        history.record(template("two"))
        with pytest.raises(NotFound):
            history.find(1)


class TestRollback:
    def test_rollback_reapplies_under_a_new_number(self):
        history = History(name="web")
        history.record(template("good"))
        history.record(template("bad"))
        roll = history.rollback_to(1, replicas=3)
        assert roll.revision == 3
        assert roll.template.label_map()["build"] == "good"

    def test_rollback_is_recorded_with_its_note(self):
        history = History(name="web")
        history.record(template("good"))
        history.record(template("bad"))
        history.rollback_to(1, replicas=3)
        assert history.current().note == "rollback of r1"

    def test_a_rollback_rolls_out_like_anything_else(self):
        history = History(name="web")
        history.record(template("good"))
        history.record(template("bad"))
        roller = Roller()
        store = Store()
        bad = history.rollout(replicas=2)
        for ordinal in range(2):
            task = Task(spec=roller._stamped(bad, ordinal))
            task.bound_to(f"n{ordinal}")
            task.phase = "Running"
            store.add_task(task)
        back = history.rollback_to(1, replicas=2)
        for _ in range(12):
            what = roller.step(store, back)
            for held in store.tasks.values():
                if held.phase == "Pending":
                    held.phase = "Running"
            if what == "done":
                break
        builds = {
            task.spec.label_map()["build"] for task in store.tasks.values()
        }
        assert builds == {"good"}

    def test_rollout_uses_the_current_entry(self):
        history = History(name="web")
        history.record(template("only"))
        roll = history.rollout(replicas=5, max_surge=2)
        assert roll.revision == 1 and roll.max_surge == 2
