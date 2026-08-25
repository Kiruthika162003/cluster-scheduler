from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.explain import explain
from fleet.sched.scorers import binpack, spread
from fleet.store import Store


def cluster() -> Store:
    store = Store()
    for number in range(3):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    return store


def task(name: str = "t", cpu: int = 200) -> Task:
    return Task(spec=TaskSpec(name=name, needs=Resources(cpu=cpu, memory=cpu)))


class TestExplanation:
    def test_every_node_appears_exactly_once(self):
        store = cluster()
        told = explain(Scheduler(scorers=(spread,)), store, task())
        assert [held.node for held in told.candidacies] == ["n0", "n1", "n2"]

    def test_refusals_carry_the_filter_sentence(self):
        store = cluster()
        told = explain(Scheduler(), store, task(cpu=5000))
        assert all("cpu" in held.refusal for held in told.candidacies)
        assert told.chosen() is None

    def test_scores_are_itemised_by_scorer_name(self):
        store = cluster()
        told = explain(Scheduler(scorers=(binpack, spread)), store, task())
        names = [name for name, _ in told.candidacies[0].scores]
        assert names == ["binpack", "spread"]

    def test_the_explainer_agrees_with_the_scheduler(self):
        store = cluster()
        tenant = task("tenant", cpu=500)
        tenant.bound_to("n1")
        store.add_task(tenant)
        scheduler = Scheduler(scorers=(binpack,))
        newcomer = task("new")
        store.add_task(newcomer)
        told = explain(scheduler, store, newcomer)
        chosen = scheduler.schedule(store, newcomer)
        assert told.chosen() == chosen.name == "n1"

    def test_the_table_marks_the_winner(self):
        store = cluster()
        told = explain(Scheduler(scorers=(spread,)), store, task())
        assert "<- chosen" in told.table()

    def test_a_fully_refused_table_has_no_marker(self):
        store = cluster()
        told = explain(Scheduler(), store, task(cpu=5000))
        assert "<- chosen" not in told.table()
        assert "refused" in told.table()
