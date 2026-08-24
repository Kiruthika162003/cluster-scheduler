from __future__ import annotations

import pytest

from fleet.errors import Unschedulable
from fleet.objects import Node, Resources, Taint, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.filters import fits, repelled_by_peers, tolerates_taints
from fleet.sched.scorers import binpack, peer_spread, spread
from fleet.store import Store


def node(name: str, cpu: int = 1000, memory: int = 1000, **kw) -> Node:
    return Node(name=name, capacity=Resources(cpu=cpu, memory=memory), **kw)


def task(name: str, cpu: int = 100, memory: int = 100, **kw) -> Task:
    return Task(spec=TaskSpec(name=name, needs=Resources(cpu=cpu, memory=memory), **kw))


class TestFilters:
    def test_fits_names_the_scarce_axis(self):
        big = task("t", cpu=2000)
        assert "cpu" in fits(big, node("n"), [])
        wide = task("t", memory=2000)
        assert "memory" in fits(wide, node("n"), [])

    def test_fits_counts_existing_tenants(self):
        tenant = task("a", cpu=900)
        tenant.bound_to("n")
        assert fits(task("b", cpu=200), node("n"), [tenant]) is not None

    def test_untolerated_taints_refuse(self):
        tainted = node("n", taints=(Taint(key="gpu", effect="NoSchedule"),))
        assert tolerates_taints(task("t"), tainted, []) is not None
        assert tolerates_taints(task("t", tolerates=("gpu",)), tainted, []) is None

    def test_prefer_no_schedule_does_not_refuse(self):
        soft = node("n", taints=(Taint(key="gpu", effect="PreferNoSchedule"),))
        assert tolerates_taints(task("t"), soft, []) is None

    def test_anti_affinity_repels_same_label_peers(self):
        peer = task("a", labels=(("app", "web"),))
        peer.bound_to("n")
        rival = task("b", labels=(("app", "web"),), repels=("app",))
        assert repelled_by_peers(rival, node("n"), [peer]) is not None
        stranger = task("c", labels=(("app", "db"),), repels=("app",))
        assert repelled_by_peers(stranger, node("n"), [peer]) is None


class TestScorers:
    def test_spread_prefers_the_empty_node(self):
        tenant = task("a", cpu=500, memory=500)
        tenant.bound_to("full")
        empty, fullish = node("empty"), node("full")
        assert spread(task("b"), empty, [tenant]) > spread(task("b"), fullish, [tenant])

    def test_binpack_prefers_the_full_node(self):
        tenant = task("a", cpu=500, memory=500)
        tenant.bound_to("full")
        empty, fullish = node("empty"), node("full")
        assert binpack(task("b"), fullish, [tenant]) > binpack(task("b"), empty, [tenant])

    def test_peer_spread_counts_same_app_tenants(self):
        peer = task("a", labels=(("app", "web"),))
        peer.bound_to("n")
        mine = task("b", labels=(("app", "web"),))
        alone = node("m")
        assert peer_spread(mine, alone, [peer]) > peer_spread(mine, node("n"), [peer])


class TestScheduler:
    def one_cluster(self) -> Store:
        store = Store()
        for name in ("n0", "n1", "n2"):
            store.add_node(node(name))
        return store

    def test_spread_walks_the_nodes(self):
        store = self.one_cluster()
        for number in range(3):
            store.add_task(task(f"t{number}", cpu=300, memory=300))
        Scheduler(scorers=(spread,)).schedule_pending(store)
        assert {t.node for t in store.active_tasks()} == {"n0", "n1", "n2"}

    def test_binpack_stacks_one_node(self):
        store = self.one_cluster()
        for number in range(3):
            store.add_task(task(f"t{number}", cpu=300, memory=300))
        Scheduler(scorers=(binpack,)).schedule_pending(store)
        assert {t.node for t in store.active_tasks()} == {"n0"}

    def test_unschedulable_carries_every_reason(self):
        store = self.one_cluster()
        wanted = task("t", cpu=5000)
        store.add_task(wanted)
        with pytest.raises(Unschedulable) as caught:
            Scheduler().schedule(store, wanted)
        assert set(caught.value.reasons) == {"n0", "n1", "n2"}

    def test_priority_orders_the_queue(self):
        store = Store()
        store.add_node(node("n0", cpu=300, memory=300))
        store.add_task(task("cheap", cpu=300, memory=300, priority=1))
        store.add_task(task("dear", cpu=300, memory=300, priority=9))
        placed, stuck = Scheduler().schedule_pending(store)
        assert placed == 1 and stuck == 1
        assert store.get_task("dear").node == "n0"
        assert store.get_task("cheap").phase == "Pending"

    def test_scheduling_is_deterministic(self):
        def run() -> dict[str, str | None]:
            store = self.one_cluster()
            for number in range(6):
                store.add_task(task(f"t{number}", cpu=200, memory=200))
            Scheduler(scorers=(spread,)).schedule_pending(store)
            return {t.spec.name: t.node for t in store.active_tasks()}

        assert run() == run()

    def test_the_meters_count(self):
        store = self.one_cluster()
        store.add_task(task("ok"))
        store.add_task(task("no", cpu=9000))
        sched = Scheduler()
        sched.schedule_pending(store)
        assert sched.placed == 1 and sched.rejected == 1
        assert "no" in sched.reasons_kept
