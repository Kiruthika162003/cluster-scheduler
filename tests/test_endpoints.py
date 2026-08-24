from __future__ import annotations

from fleet.control.endpoints import Readiness, Service, endpoints
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def served_store() -> Store:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    store.add_node(Node(name="n1", capacity=Resources(cpu=1000, memory=1000)))
    for number, node in enumerate(["n0", "n0", "n1"]):
        task = Task(
            spec=TaskSpec(
                name=f"web-{number}",
                needs=Resources(cpu=100, memory=100),
                labels=(("app", "web"),),
            )
        )
        task.bound_to(node)
        task.phase = "Running"
        store.add_task(task)
    loner = Task(spec=TaskSpec(name="other", needs=Resources(cpu=1, memory=1)))
    loner.bound_to("n0")
    loner.phase = "Running"
    store.add_task(loner)
    return store


def web() -> Service:
    return Service(name="web-svc", selector_key="app", selector_value="web")


class TestEndpoints:
    def test_selected_running_tasks_are_endpoints(self):
        store = served_store()
        assert endpoints(store, web(), Readiness(), now=0) == [
            "web-0", "web-1", "web-2",
        ]

    def test_unselected_tasks_never_appear(self):
        store = served_store()
        assert "other" not in endpoints(store, web(), Readiness(), now=0)

    def test_a_pending_task_is_not_an_endpoint(self):
        store = served_store()
        held = store.get_task("web-1")
        held.phase = "Pending"
        held.node = None
        assert endpoints(store, web(), Readiness(), now=0) == ["web-0", "web-2"]

    def test_a_dead_node_takes_its_endpoints_with_it(self):
        store = served_store()
        store.get_node("n0").ready = False
        assert endpoints(store, web(), Readiness(), now=0) == ["web-2"]

    def test_readiness_removes_without_killing(self):
        store = served_store()
        readiness = Readiness(unready_at={"web-0": frozenset({5, 6})})
        assert "web-0" not in endpoints(store, web(), readiness, now=5)
        assert store.get_task("web-0").phase == "Running"
        assert store.get_task("web-0").restarts == 0

    def test_the_endpoint_returns_when_ready_again(self):
        store = served_store()
        readiness = Readiness(unready_at={"web-0": frozenset({5})})
        endpoints(store, web(), readiness, now=5)
        assert "web-0" in endpoints(store, web(), readiness, now=6)
        assert readiness.removals == 1 and readiness.returns == 1

    def test_a_cordoned_node_keeps_serving_endpoints(self):
        store = served_store()
        store.get_node("n0").schedulable = False
        told = endpoints(store, web(), Readiness(), now=0)
        assert told == ["web-0", "web-1", "web-2"]
