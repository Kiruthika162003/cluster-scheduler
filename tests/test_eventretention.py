from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.eventretention import RetentionKeeper
from fleet.objects import Resources, Task, TaskSpec
from fleet.store import Store
from fleet.subscriptions import subscribe


def busy_store(events: int = 10) -> Store:
    store = Store()
    for number in range(events):
        store.add_task(
            Task(
                spec=TaskSpec(
                    name=f"t{number}", needs=Resources(cpu=1, memory=1)
                )
            )
        )
    return store


class TestCompaction:
    def test_compaction_removes_only_the_agreed_prefix(self):
        store = busy_store()
        keeper = RetentionKeeper()
        keeper.register("fast", cursor=8)
        removed = keeper.compact(store, keep_from=5)
        assert removed == 5
        assert store.events[0].sequence == 5

    def test_the_laggard_blocks_compaction_by_name(self):
        store = busy_store()
        keeper = RetentionKeeper()
        keeper.register("fast", cursor=9)
        keeper.register("slow", cursor=2)
        with pytest.raises(Invalid) as caught:
            keeper.compact(store, keep_from=5)
        assert "strand slow at cursor 2" in str(caught.value)

    def test_advancing_the_laggard_unblocks(self):
        store = busy_store()
        keeper = RetentionKeeper()
        keeper.register("slow", cursor=2)
        keeper.advance("slow", cursor=7)
        assert keeper.compact(store, keep_from=5) == 5

    def test_expulsion_is_the_other_door(self):
        store = busy_store()
        keeper = RetentionKeeper()
        keeper.register("slow", cursor=1)
        keeper.expel("slow")
        assert keeper.compact(store, keep_from=6) == 6
        assert keeper.expelled == ["slow"]

    def test_recompacting_below_the_line_is_a_no_op(self):
        store = busy_store()
        keeper = RetentionKeeper()
        keeper.compact(store, keep_from=4)
        assert keeper.compact(store, keep_from=3) == 0


class TestSubscribersSurvive:
    def test_a_subscriber_above_the_compaction_resumes_cleanly(self):
        store = busy_store()
        watcher = subscribe("all")
        watcher.pull(store)
        keeper = RetentionKeeper()
        keeper.register("all", watcher.cursor)
        keeper.compact(store, keep_from=watcher.cursor)
        store.add_task(
            Task(spec=TaskSpec(name="fresh", needs=Resources(cpu=1, memory=1)))
        )
        events = watcher.pull(store)
        assert [event.name for event in events] == ["fresh"]

    def test_the_laggard_query_names_the_slowest(self):
        keeper = RetentionKeeper()
        keeper.register("a", 5)
        keeper.register("b", 3)
        assert keeper.laggard() == ("b", 3)
