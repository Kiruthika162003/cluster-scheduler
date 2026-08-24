from __future__ import annotations

from fleet.control.daemons import DaemonKeeper, DaemonSpec
from fleet.objects import Node, Resources, TaskSpec
from fleet.store import Store


def spec() -> DaemonSpec:
    return DaemonSpec(
        name="logship",
        template=TaskSpec(name="tpl", needs=Resources(cpu=50, memory=50)),
    )


def cluster(count: int = 3) -> Store:
    store = Store()
    for number in range(count):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    return store


class TestDaemons:
    def test_every_node_gets_its_daemon(self):
        store = cluster()
        keeper = DaemonKeeper()
        created, removed = keeper.reconcile(store, spec())
        assert created == 3 and removed == 0
        assert sorted(store.tasks) == ["logship-n0", "logship-n1", "logship-n2"]

    def test_daemons_bind_to_their_namesake(self):
        store = cluster()
        DaemonKeeper().reconcile(store, spec())
        assert store.get_task("logship-n1").node == "n1"
        assert store.get_task("logship-n1").phase == "Bound"

    def test_a_joining_node_is_covered_on_the_next_pass(self):
        store = cluster()
        keeper = DaemonKeeper()
        keeper.reconcile(store, spec())
        store.add_node(Node(name="n9", capacity=Resources(cpu=1000, memory=1000)))
        created, _ = keeper.reconcile(store, spec())
        assert created == 1
        assert store.get_task("logship-n9").node == "n9"

    def test_a_leaving_node_strands_its_daemon_and_it_goes(self):
        store = cluster()
        keeper = DaemonKeeper()
        keeper.reconcile(store, spec())
        store.remove_node("n2")
        _, removed = keeper.reconcile(store, spec())
        assert removed == 1
        assert "logship-n2" not in store.tasks

    def test_a_cordoned_node_keeps_its_daemon(self):
        store = cluster()
        keeper = DaemonKeeper()
        keeper.reconcile(store, spec())
        store.get_node("n1").schedulable = False
        created, removed = keeper.reconcile(store, spec())
        assert created == 0 and removed == 0
        assert "logship-n1" in store.tasks

    def test_reconcile_is_idempotent(self):
        store = cluster()
        keeper = DaemonKeeper()
        keeper.reconcile(store, spec())
        writes = store.writes
        assert keeper.reconcile(store, spec()) == (0, 0)
        assert store.writes == writes

    def test_the_log_reads_like_a_story(self):
        store = cluster(count=1)
        keeper = DaemonKeeper()
        keeper.reconcile(store, spec())
        store.remove_node("n0")
        keeper.reconcile(store, spec())
        assert keeper.log == [
            "logship-n0 follows n0",
            "logship-n0 stranded, removed",
        ]
