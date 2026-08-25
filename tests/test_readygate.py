from __future__ import annotations

from fleet.control.endpoints import Readiness, Service
from fleet.control.readygate import ReadyGate
from fleet.depends import DependencyGraph
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def platform() -> tuple[Store, ReadyGate]:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=4000, memory=4000)))
    for name, app in (("web-0", "web"), ("db-0", "db")):
        task = Task(
            spec=TaskSpec(
                name=name,
                needs=Resources(cpu=100, memory=100),
                labels=(("app", app),),
            )
        )
        task.bound_to("n0")
        task.phase = "Running"
        store.add_task(task)
    graph = DependencyGraph()
    graph.declare("web", "db")
    gate = ReadyGate(graph=graph)
    gate.register(Service(name="web", selector_key="app", selector_value="web"))
    gate.register(Service(name="db", selector_key="app", selector_value="db"))
    return store, gate


class TestGating:
    def test_a_healthy_platform_gates_nothing(self):
        store, gate = platform()
        assert gate.gated_services(store, Readiness(), now=0) == set()
        assert gate.effective_endpoints(store, "web", Readiness(), 0) == ["web-0"]

    def test_a_dead_dependency_gates_the_dependent(self):
        store, gate = platform()
        store.get_task("db-0").phase = "Pending"
        assert gate.gated_services(store, Readiness(), now=1) == {"web"}
        assert gate.effective_endpoints(store, "web", Readiness(), 1) == []

    def test_the_dependent_task_is_not_restarted(self):
        store, gate = platform()
        store.get_task("db-0").phase = "Pending"
        gate.gated_services(store, Readiness(), now=1)
        held = store.get_task("web-0")
        assert held.phase == "Running" and held.restarts == 0

    def test_recovery_releases_the_gate(self):
        store, gate = platform()
        store.get_task("db-0").phase = "Pending"
        gate.gated_services(store, Readiness(), now=1)
        store.get_task("db-0").phase = "Running"
        assert gate.gated_services(store, Readiness(), now=2) == set()
        assert gate.transitions == ["[1] web gated", "[2] web released"]

    def test_the_leaf_service_is_never_gated_by_itself(self):
        store, gate = platform()
        store.get_task("db-0").phase = "Pending"
        gated = gate.gated_services(store, Readiness(), now=1)
        assert "db" not in gated

    def test_readiness_probes_compose_with_the_gate(self):
        store, gate = platform()
        readiness = Readiness(unready_at={"db-0": frozenset({5})})
        assert gate.effective_endpoints(store, "web", readiness, 5) == []
        assert gate.effective_endpoints(store, "web", readiness, 6) == ["web-0"]
