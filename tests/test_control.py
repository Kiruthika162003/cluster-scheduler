from __future__ import annotations

from fleet.control.budget import Budget, Guard
from fleet.control.deploy import Deployer, DeploySpec
from fleet.control.nodes import EVICT_AFTER, NOT_READY_AFTER, Monitor
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def store_with_node(name: str = "n0") -> Store:
    store = Store()
    store.add_node(Node(name=name, capacity=Resources(cpu=1000, memory=1000)))
    return store


def template() -> TaskSpec:
    return TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100))


def bound_task(name: str, node: str, labels: tuple = ()) -> Task:
    task = Task(spec=TaskSpec(name=name, needs=Resources(cpu=10, memory=10), labels=labels))
    task.bound_to(node)
    return task


class TestDeployer:
    def test_scale_up_creates_the_missing(self):
        store = Store()
        deployer = Deployer()
        created, deleted = deployer.reconcile(
            store, DeploySpec(name="web", replicas=3, template=template())
        )
        assert created == 3 and deleted == 0
        assert sorted(store.tasks) == ["web-0", "web-1", "web-2"]

    def test_children_carry_the_deploy_label(self):
        store = Store()
        Deployer().reconcile(store, DeploySpec(name="web", replicas=1, template=template()))
        assert store.get_task("web-0").spec.label_map()["deploy"] == "web"

    def test_scale_down_deletes_the_surplus(self):
        store = Store()
        deployer = Deployer()
        deployer.reconcile(store, DeploySpec(name="web", replicas=3, template=template()))
        deployer.reconcile(store, DeploySpec(name="web", replicas=1, template=template()))
        assert sorted(store.tasks) == ["web-0"]

    def test_reconcile_of_a_converged_deploy_is_a_no_op(self):
        store = Store()
        deployer = Deployer()
        spec = DeploySpec(name="web", replicas=2, template=template())
        deployer.reconcile(store, spec)
        writes = store.writes
        assert deployer.reconcile(store, spec) == (0, 0)
        assert store.writes == writes

    def test_a_matching_orphan_is_adopted_not_duplicated(self):
        store = Store()
        stray = Task(
            spec=TaskSpec(
                name="stray",
                needs=Resources(cpu=1, memory=1),
                labels=(("deploy", "web"),),
            )
        )
        store.add_task(stray)
        deployer = Deployer()
        created, _ = deployer.reconcile(
            store, DeploySpec(name="web", replicas=1, template=template())
        )
        assert created == 0 and deployer.adopted == 1

    def test_finished_children_do_not_count_toward_replicas(self):
        store = Store()
        deployer = Deployer()
        spec = DeploySpec(name="web", replicas=2, template=template())
        deployer.reconcile(store, spec)
        done = store.get_task("web-0")
        done.phase = "Succeeded"
        assert not deployer.converged(store, spec)


class TestMonitor:
    def test_a_quiet_node_turns_not_ready(self):
        store = store_with_node()
        monitor = Monitor()
        turned, _ = monitor.sweep(store, now=NOT_READY_AFTER + 1)
        assert turned == 1 and not store.get_node("n0").ready

    def test_a_heartbeat_restores_readiness(self):
        store = store_with_node()
        monitor = Monitor()
        monitor.sweep(store, now=NOT_READY_AFTER + 1)
        monitor.beat(store, "n0", now=NOT_READY_AFTER + 2)
        assert store.get_node("n0").ready and monitor.marked_ready == 1

    def test_tasks_survive_short_silences(self):
        store = store_with_node()
        store.add_task(bound_task("t", "n0"))
        monitor = Monitor()
        _, evicted = monitor.sweep(store, now=EVICT_AFTER)
        assert evicted == 0
        assert store.get_task("t").phase == "Bound"

    def test_long_silence_requeues_the_tasks(self):
        store = store_with_node()
        store.add_task(bound_task("t", "n0"))
        monitor = Monitor()
        _, evicted = monitor.sweep(store, now=EVICT_AFTER + 1)
        assert evicted == 1
        held = store.get_task("t")
        assert held.phase == "Pending" and held.node is None and held.restarts == 1

    def test_a_returning_node_keeps_its_tasks(self):
        store = store_with_node()
        store.add_task(bound_task("t", "n0"))
        monitor = Monitor()
        monitor.sweep(store, now=NOT_READY_AFTER + 1)
        monitor.beat(store, "n0", now=NOT_READY_AFTER + 2)
        _, evicted = monitor.sweep(store, now=NOT_READY_AFTER + 3)
        assert evicted == 0 and store.get_task("t").node == "n0"


class TestGuard:
    def guarded_store(self) -> tuple[Store, Guard]:
        store = store_with_node("a")
        store.add_node(Node(name="b", capacity=Resources(cpu=1000, memory=1000)))
        for number, node in enumerate(["a", "a", "b"]):
            store.add_task(
                bound_task(f"w{number}", node, labels=(("app", "web"),))
            )
        guard = Guard(
            budgets=[
                Budget(
                    name="web-floor",
                    selector_key="app",
                    selector_value="web",
                    min_available=2,
                )
            ]
        )
        return store, guard

    def test_an_eviction_above_the_floor_is_allowed(self):
        store, guard = self.guarded_store()
        may, _ = guard.may_evict(store, "w0")
        assert may

    def test_the_floor_refuses_the_last_evictions(self):
        store, guard = self.guarded_store()
        evicted, refused = guard.drain(store, "a")
        assert len(evicted) == 1 and len(refused) == 1
        assert guard.refused == 1

    def test_uncovered_tasks_are_never_refused(self):
        store, guard = self.guarded_store()
        store.add_task(bound_task("lone", "a"))
        may, _ = guard.may_evict(store, "lone")
        assert may

    def test_a_drain_of_an_empty_node_does_nothing(self):
        store, guard = self.guarded_store()
        assert guard.drain(store, "ghost") == ([], [])
