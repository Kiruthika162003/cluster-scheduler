from __future__ import annotations

from fleet.control.ordinals import OrdinalKeeper, OrdinalSpec
from fleet.objects import Resources, TaskSpec
from fleet.store import Store


def spec(count: int = 3, revision: int = 1) -> OrdinalSpec:
    return OrdinalSpec(
        name="db",
        count=count,
        revision=revision,
        template=TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100)),
    )


def run_all(store: Store, keeper: OrdinalKeeper, target: OrdinalSpec) -> list[str]:
    steps = []
    for _ in range(20):
        what = keeper.reconcile(store, target)
        steps.append(what)
        for task in store.tasks.values():
            if task.phase == "Pending":
                task.phase = "Running"
        if what == "settled":
            break
    return steps


class TestBirth:
    def test_ordinals_are_born_in_order(self):
        store = Store()
        keeper = OrdinalKeeper()
        run_all(store, keeper, spec())
        assert keeper.log == ["born db-0", "born db-1", "born db-2"]

    def test_an_ordinal_waits_for_its_elder(self):
        store = Store()
        keeper = OrdinalKeeper()
        keeper.reconcile(store, spec())
        what = keeper.reconcile(store, spec())
        assert what == "waiting on db-0"

    def test_names_are_stable(self):
        store = Store()
        keeper = OrdinalKeeper()
        run_all(store, keeper, spec())
        assert sorted(store.tasks) == ["db-0", "db-1", "db-2"]


class TestDeathAndRebirth:
    def test_a_failed_ordinal_is_reborn_under_its_own_name(self):
        store = Store()
        keeper = OrdinalKeeper()
        run_all(store, keeper, spec())
        store.get_task("db-1").phase = "Failed"
        what = keeper.reconcile(store, spec())
        assert what == "reborn db-1"
        assert "db-1" in store.tasks

    def test_shrink_retires_from_the_top(self):
        store = Store()
        keeper = OrdinalKeeper()
        run_all(store, keeper, spec())
        run_all(store, keeper, spec(count=2))
        assert sorted(store.tasks) == ["db-0", "db-1"]
        assert "retired db-2" in keeper.log


class TestUpdates:
    def test_updates_replace_top_down_one_at_a_time(self):
        store = Store()
        keeper = OrdinalKeeper()
        run_all(store, keeper, spec())
        run_all(store, keeper, spec(revision=2))
        replaced = [line for line in keeper.log if line.startswith("replaced")]
        assert replaced == [
            "replaced db-2 at r2",
            "replaced db-1 at r2",
            "replaced db-0 at r2",
        ]

    def test_a_replacement_keeps_the_name_and_the_new_revision(self):
        store = Store()
        keeper = OrdinalKeeper()
        run_all(store, keeper, spec())
        run_all(store, keeper, spec(revision=2))
        held = store.get_task("db-0")
        assert held.spec.label_map()["revision"] == "2"

    def test_a_settled_set_stays_settled(self):
        store = Store()
        keeper = OrdinalKeeper()
        run_all(store, keeper, spec())
        writes = store.writes
        assert keeper.reconcile(store, spec()) == "settled"
        assert store.writes == writes
