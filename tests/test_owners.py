from __future__ import annotations

import pytest

from fleet.control.owners import Owners
from fleet.errors import Invalid, NotFound
from fleet.objects import Resources, Task, TaskSpec
from fleet.store import Store


def task(name: str) -> Task:
    return Task(spec=TaskSpec(name=name, needs=Resources(cpu=1, memory=1)))


def family() -> tuple[Store, Owners]:
    store = Store()
    owners = Owners()
    for name in ("root", "mid", "leaf-a", "leaf-b", "stranger"):
        store.add_task(task(name))
    owners.link("mid", "root")
    owners.link("leaf-a", "mid")
    owners.link("leaf-b", "mid")
    return store, owners


class TestLinking:
    def test_self_ownership_is_refused(self):
        with pytest.raises(Invalid):
            Owners().link("a", "a")

    def test_a_cycle_is_refused_at_link_time(self):
        owners = Owners()
        owners.link("b", "a")
        owners.link("c", "b")
        with pytest.raises(Invalid):
            owners.link("a", "c")

    def test_children_are_listed_sorted(self):
        _, owners = family()
        assert owners.children_of("mid") == ["leaf-a", "leaf-b"]


class TestCascade:
    def test_the_subtree_goes_leaves_first(self):
        store, owners = family()
        removed = owners.delete_cascading(store, "root")
        assert removed == ["leaf-a", "leaf-b", "mid", "root"]

    def test_strangers_survive_the_cascade(self):
        store, owners = family()
        owners.delete_cascading(store, "root")
        assert sorted(store.tasks) == ["stranger"]

    def test_a_mid_delete_takes_only_its_branch(self):
        store, owners = family()
        owners.delete_cascading(store, "mid")
        assert sorted(store.tasks) == ["root", "stranger"]

    def test_references_are_cleaned_up(self):
        store, owners = family()
        owners.delete_cascading(store, "root")
        assert owners.owner_of == {}


class TestOrphaning:
    def test_children_survive_and_are_freed(self):
        store, owners = family()
        freed = owners.delete_orphaning(store, "mid")
        assert freed == ["leaf-a", "leaf-b"]
        assert "leaf-a" in store.tasks
        assert "leaf-a" not in owners.owner_of

    def test_the_owner_itself_is_gone(self):
        store, owners = family()
        owners.delete_orphaning(store, "mid")
        assert "mid" not in store.tasks

    def test_orphaning_a_ghost_is_not_found(self):
        store, owners = family()
        store.remove_task("mid")
        with pytest.raises(NotFound):
            owners.delete_orphaning(store, "mid")

    def test_grandchildren_keep_their_parents(self):
        store, owners = family()
        owners.delete_orphaning(store, "root")
        assert owners.owner_of == {"leaf-a": "mid", "leaf-b": "mid"}
