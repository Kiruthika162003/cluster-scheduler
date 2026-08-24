from __future__ import annotations

import pytest

from fleet.errors import Unschedulable
from fleet.nodepools import Pools, PoolSpec
from fleet.objects import Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.store import Store


def pooled_store() -> tuple[Store, Pools, PoolSpec, PoolSpec]:
    store = Store()
    pools = Pools()
    general = PoolSpec(
        name="general", count=3, shape=Resources(cpu=1000, memory=1000)
    )
    gpu = PoolSpec(
        name="gpu", count=2, shape=Resources(cpu=4000, memory=8000), dedicated=True
    )
    pools.provision(store, general)
    pools.provision(store, gpu)
    return store, pools, general, gpu


def plain_task(name: str) -> Task:
    return Task(spec=TaskSpec(name=name, needs=Resources(cpu=500, memory=500)))


class TestProvisioning:
    def test_nodes_arrive_labelled(self):
        store, _, _, _ = pooled_store()
        assert store.get_node("general-0").labels["pool"] == "general"

    def test_dedicated_pools_are_tainted(self):
        store, _, _, _ = pooled_store()
        assert store.get_node("gpu-0").taints
        assert not store.get_node("general-0").taints


class TestFencing:
    def test_the_general_population_stays_out(self):
        store, _, _, _ = pooled_store()
        scheduler = Scheduler()
        for number in range(6):
            task = plain_task(f"t{number}")
            store.add_task(task)
        scheduler.schedule_pending(store)
        homes = {task.node for task in store.active_tasks()}
        assert all(home.startswith("general") for home in homes)

    def test_overflow_is_refused_not_leaked(self):
        store, _, _, _ = pooled_store()
        scheduler = Scheduler()
        big = Task(spec=TaskSpec(name="big", needs=Resources(cpu=2000, memory=2000)))
        store.add_task(big)
        with pytest.raises(Unschedulable) as caught:
            scheduler.schedule(store, big)
        assert "untolerated taint" in str(caught.value)

    def test_the_resident_insists_and_tolerates(self):
        store, pools, _, gpu = pooled_store()
        base = TaskSpec(name="train", needs=Resources(cpu=3000, memory=4000))
        resident = pools.resident_spec(gpu, base)
        task = Task(spec=resident)
        store.add_task(task)
        Scheduler().schedule(store, task)
        assert task.node.startswith("gpu")

    def test_the_resident_never_slums(self):
        store, pools, _, gpu = pooled_store()
        base = TaskSpec(name="train", needs=Resources(cpu=100, memory=100))
        resident = pools.resident_spec(gpu, base)
        task = Task(spec=resident)
        store.add_task(task)
        Scheduler().schedule(store, task)
        assert task.node.startswith("gpu")


class TestHeadroom:
    def test_headroom_is_answered_per_pool(self):
        store, pools, _, _ = pooled_store()
        task = plain_task("t")
        task.bound_to("general-0")
        store.add_task(task)
        general = pools.headroom(store, "general")
        gpu = pools.headroom(store, "gpu")
        assert general.cpu == 3 * 1000 - 500
        assert gpu.cpu == 2 * 4000

    def test_unready_nodes_offer_nothing(self):
        store, pools, _, _ = pooled_store()
        store.get_node("general-0").ready = False
        assert pools.headroom(store, "general").cpu == 2000
