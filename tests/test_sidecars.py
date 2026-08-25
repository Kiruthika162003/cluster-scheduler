from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sidecars import SidecarKeeper
from fleet.store import Store


def primary_on(node: str) -> Store:
    store = Store()
    for name in ("n0", "n1"):
        store.add_node(Node(name=name, capacity=Resources(cpu=1000, memory=1000)))
    task = Task(spec=TaskSpec(name="web", needs=Resources(cpu=300, memory=300)))
    task.bound_to(node)
    store.add_task(task)
    return store


class TestAttachment:
    def test_the_sidecar_carries_the_link_label(self):
        store = primary_on("n0")
        keeper = SidecarKeeper()
        name = keeper.attach(store, "web", Resources(cpu=50, memory=50))
        assert name == "web-side"
        assert store.get_task(name).spec.label_map()["sidecar-of"] == "web"


class TestTheContract:
    def test_placement_follows_the_primary(self):
        store = primary_on("n0")
        keeper = SidecarKeeper()
        keeper.attach(store, "web", Resources(cpu=50, memory=50))
        actions = keeper.reconcile(store)
        assert actions == ["web-side follows web to n0"]
        assert store.get_task("web-side").node == "n0"

    def test_a_moved_primary_pulls_the_sidecar(self):
        store = primary_on("n0")
        keeper = SidecarKeeper()
        keeper.attach(store, "web", Resources(cpu=50, memory=50))
        keeper.reconcile(store)
        primary = store.get_task("web")
        generation = primary.generation
        primary.node = "n1"
        store.update_task(primary, read_generation=generation)
        keeper.reconcile(store)
        assert store.get_task("web-side").node == "n1"

    def test_an_evicted_primary_takes_the_sidecar_down(self):
        store = primary_on("n0")
        keeper = SidecarKeeper()
        keeper.attach(store, "web", Resources(cpu=50, memory=50))
        keeper.reconcile(store)
        primary = store.get_task("web")
        generation = primary.generation
        primary.phase = "Pending"
        primary.node = None
        store.update_task(primary, read_generation=generation)
        actions = keeper.reconcile(store)
        assert actions == ["web-side shares the fate of web"]
        held = store.get_task("web-side")
        assert held.phase == "Pending" and held.node is None

    def test_a_finished_primary_cleans_up_its_companion(self):
        store = primary_on("n0")
        keeper = SidecarKeeper()
        keeper.attach(store, "web", Resources(cpu=50, memory=50))
        keeper.reconcile(store)
        primary = store.get_task("web")
        generation = primary.generation
        primary.phase = "Succeeded"
        primary.node = None
        store.update_task(primary, read_generation=generation)
        actions = keeper.reconcile(store)
        assert actions == ["web-side removed with its primary"]
        assert "web-side" not in store.tasks

    def test_a_deleted_primary_cleans_up_too(self):
        store = primary_on("n0")
        keeper = SidecarKeeper()
        keeper.attach(store, "web", Resources(cpu=50, memory=50))
        keeper.reconcile(store)
        store.remove_task("web")
        keeper.reconcile(store)
        assert "web-side" not in store.tasks
        assert keeper.removed == 1
