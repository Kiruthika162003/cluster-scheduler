from __future__ import annotations

import pytest

from fleet.control.retryloop import RetryLoop
from fleet.errors import Conflict
from fleet.objects import Resources, Task, TaskSpec
from fleet.store import Store


def store_with(name: str = "t") -> Store:
    store = Store()
    store.add_task(Task(spec=TaskSpec(name=name, needs=Resources(cpu=1, memory=1))))
    return store


class TestQuietEdits:
    def test_an_uncontended_edit_lands_first_try(self):
        store = store_with()
        loop = RetryLoop()
        got = loop.edit(store, "t", lambda task: setattr(task, "phase", "Bound"))
        assert got.phase == "Bound"
        assert loop.attempts_spent == 1 and loop.conflicts_absorbed == 0

    def test_the_edit_returns_the_written_object(self):
        store = store_with()
        got = RetryLoop().edit(store, "t", lambda task: setattr(task, "node", "n0"))
        assert store.get_task("t").node == "n0" and got.node == "n0"


class TestContention:
    def test_a_racing_write_is_absorbed_and_survives(self):
        store = store_with()
        loop = RetryLoop()
        interfered = []

        def change(task: Task) -> None:
            if not interfered:
                interfered.append(True)
                rival = store.get_task("t")
                generation = rival.generation
                rival.restarts = 7
                store.update_task(rival, read_generation=generation)
            task.phase = "Bound"

        got = loop.edit(store, "t", change)
        assert got.phase == "Bound"
        assert got.restarts == 7
        assert loop.conflicts_absorbed == 1 and loop.attempts_spent == 2

    def test_the_redecision_sees_the_new_truth(self):
        store = store_with()
        seen = []

        def change(task: Task) -> None:
            seen.append(task.restarts)
            if len(seen) == 1:
                rival = store.get_task("t")
                generation = rival.generation
                rival.restarts = 42
                store.update_task(rival, read_generation=generation)
            task.phase = "Bound"

        RetryLoop().edit(store, "t", change)
        assert seen == [0, 42]

    def test_endless_contention_errors_with_the_count(self):
        store = store_with()
        loop = RetryLoop(attempts_allowed=3)

        def change(task: Task) -> None:
            rival = store.get_task("t")
            generation = rival.generation
            rival.restarts += 1
            store.update_task(rival, read_generation=generation)
            task.phase = "Bound"

        with pytest.raises(Conflict) as caught:
            loop.edit(store, "t", change)
        assert "3 attempts" in str(caught.value)
        assert loop.conflicts_absorbed == 3
