from __future__ import annotations

from fleet.objects import Resources, Task, TaskSpec
from fleet.registrygc import (
    DigestStore,
    collect,
    history_references,
    running_references,
)
from fleet.roll.history import History
from fleet.store import Store


def imaged_spec(image: str) -> TaskSpec:
    return TaskSpec(
        name="tpl", needs=Resources(cpu=1, memory=1), labels=(("image", image),)
    )


def running_web(image: str) -> Store:
    store = Store()
    task = Task(
        spec=TaskSpec(
            name="web-0",
            needs=Resources(cpu=1, memory=1),
            labels=(("image", image),),
        )
    )
    task.bound_to("n0")
    store.add_task(task)
    return store


def two_revision_history() -> History:
    history = History(name="web")
    history.record(imaged_spec("sha-v1"), note="good")
    history.record(imaged_spec("sha-v2"), note="current")
    return history


class TestReferences:
    def test_running_tasks_reference_their_image(self):
        assert running_references(running_web("sha-v2")) == {"sha-v2"}

    def test_finished_tasks_reference_nothing(self):
        store = running_web("sha-v2")
        store.get_task("web-0").phase = "Succeeded"
        assert running_references(store) == set()

    def test_history_references_every_recorded_image(self):
        held = history_references([two_revision_history()])
        assert held == {"sha-v1", "sha-v2"}

    def test_a_capped_history_forgets_with_its_entries(self):
        history = History(name="web", keep=1)
        history.record(imaged_spec("sha-v1"))
        history.record(imaged_spec("sha-v2"))
        assert history_references([history]) == {"sha-v2"}


class TestCollection:
    def scene(self) -> tuple[DigestStore, Store, list[History]]:
        registry = DigestStore()
        registry.push("sha-v1")
        registry.push("sha-v2")
        registry.push("sha-orphan")
        return registry, running_web("sha-v2"), [two_revision_history()]

    def test_the_eager_collector_deletes_the_rollback_target(self):
        registry, store, histories = self.scene()
        doomed = collect(registry, store, histories, careful=False)
        assert doomed == ["sha-orphan", "sha-v1"]
        assert not registry.holds("sha-v1")

    def test_the_careful_collector_keeps_it(self):
        registry, store, histories = self.scene()
        doomed = collect(registry, store, histories, careful=True)
        assert doomed == ["sha-orphan"]
        assert registry.holds("sha-v1")

    def test_both_collectors_take_the_true_orphan(self):
        registry, store, histories = self.scene()
        collect(registry, store, histories, careful=True)
        assert not registry.holds("sha-orphan")

    def test_deletion_is_recorded_in_order(self):
        registry, store, histories = self.scene()
        collect(registry, store, histories, careful=False)
        assert registry.deleted == ["sha-orphan", "sha-v1"]
