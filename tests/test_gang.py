from __future__ import annotations

from fleet.objects import Node, Resources
from fleet.sched.core import Scheduler
from fleet.sched.gang import Gang, GangScheduler, hostages, naive_admit
from fleet.store import Store


def cluster(nodes: int = 4, cpu: int = 1000) -> Store:
    store = Store()
    for number in range(nodes):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=cpu, memory=1000))
        )
    return store


def gang(name: str, members: int, cpu: int = 500) -> Gang:
    return Gang(name=name, members=members, each_needs=Resources(cpu=cpu, memory=100))


class TestGangSpecs:
    def test_members_are_named_and_labelled(self):
        specs = gang("train", 2).specs()
        assert [spec.name for spec in specs] == ["train-0", "train-1"]
        assert all(spec.label_map()["gang"] == "train" for spec in specs)


class TestRehearsal:
    def test_a_fitting_gang_is_admitted_whole(self):
        store = cluster()
        assert GangScheduler().admit(store, gang("train", 8))
        assert len(store.active_tasks()) == 8

    def test_an_unfitting_gang_leaves_no_trace(self):
        store = cluster()
        scheduler = GangScheduler()
        assert not scheduler.admit(store, gang("big", 9))
        assert store.tasks == {}
        assert scheduler.refused == 1

    def test_rehearsal_respects_existing_tenants(self):
        store = cluster()
        GangScheduler().admit(store, gang("first", 6))
        assert not GangScheduler().admit(store, gang("second", 3))

    def test_members_pack_where_they_fit(self):
        store = cluster(nodes=2, cpu=1000)
        assert GangScheduler().admit(store, gang("train", 4))
        nodes_used = {task.node for task in store.active_tasks()}
        assert nodes_used == {"n0", "n1"}


class TestHostages:
    def test_naive_admission_strands_partial_gangs(self):
        store = cluster()
        landed_first = naive_admit(store, Scheduler(), gang("a", 6))
        landed_second = naive_admit(store, Scheduler(), gang("b", 6))
        assert landed_first == 6 and landed_second == 2
        assert hostages(store) == {"b": 2}

    def test_a_complete_gang_is_not_a_hostage(self):
        store = cluster()
        GangScheduler().admit(store, gang("whole", 4))
        assert hostages(store) == {}

    def test_ungrouped_tasks_are_ignored(self):
        from fleet.objects import Task, TaskSpec

        store = cluster()
        loner = Task(spec=TaskSpec(name="x", needs=Resources(cpu=1, memory=1)))
        loner.bound_to("n0")
        store.add_task(loner)
        assert hostages(store) == {}
