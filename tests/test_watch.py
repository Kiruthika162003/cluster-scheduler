from __future__ import annotations

from fleet.control.watch import Informer
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def task(name: str) -> Task:
    return Task(spec=TaskSpec(name=name, needs=Resources(cpu=1, memory=1)))


def busy_store() -> Store:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=100, memory=100)))
    for number in range(5):
        store.add_task(task(f"t{number}"))
    bound = store.get_task("t0")
    bound.bound_to("n0")
    store.update_task(bound, read_generation=1)
    store.remove_task("t4")
    return store


class TestInformer:
    def test_a_fresh_informer_catches_up_in_one_replay(self):
        store = busy_store()
        informer = Informer()
        informer.refresh(store)
        assert informer.agrees_with(store)

    def test_replay_applies_only_the_unseen(self):
        store = Store()
        informer = Informer()
        store.add_task(task("a"))
        assert informer.refresh(store) == 1
        assert informer.refresh(store) == 0
        store.add_task(task("b"))
        assert informer.refresh(store) == 1

    def test_piecewise_and_wholesale_replay_agree(self):
        store = Store()
        piecewise = Informer()
        store.add_task(task("a"))
        piecewise.refresh(store)
        store.add_task(task("b"))
        held = store.get_task("a")
        held.phase = "Failed"
        store.update_task(held, read_generation=1)
        store.remove_task("b")
        piecewise.refresh(store)
        wholesale = Informer()
        wholesale.refresh(store)
        assert piecewise.known_tasks == wholesale.known_tasks
        assert piecewise.cursor == wholesale.cursor

    def test_the_cache_tracks_phases(self):
        store = busy_store()
        informer = Informer()
        informer.refresh(store)
        assert informer.phase_counts() == {"Pending": 3, "Bound": 1}

    def test_node_membership_follows_events(self):
        store = Store()
        store.add_node(Node(name="n0", capacity=Resources(cpu=1, memory=1)))
        informer = Informer()
        informer.refresh(store)
        store.remove_node("n0")
        informer.refresh(store)
        assert informer.known_nodes == set()

    def test_a_removed_task_never_lingers(self):
        store = Store()
        store.add_task(task("gone"))
        store.remove_task("gone")
        informer = Informer()
        informer.refresh(store)
        assert informer.known_tasks == {}
