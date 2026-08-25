from __future__ import annotations

from fleet.control.budget import Budget, Guard
from fleet.descheduler import Descheduler
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store
from fleet.verify import violations


def sliver_city(labelled: bool = False) -> Store:
    store = Store()
    for number in range(5):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    for number in range(5):
        labels = (("app", "web"),) if labelled else ()
        task = Task(
            spec=TaskSpec(
                name=f"t{number}",
                needs=Resources(cpu=400, memory=400),
                labels=labels,
            )
        )
        task.bound_to(f"n{number}")
        store.add_task(task)
    return store


class TestDescheduling:
    def test_unguarded_consolidation_proceeds_under_the_cap(self):
        descheduler = Descheduler(guard=Guard(), per_run_cap=3)
        store = sliver_city()
        performed, refused = descheduler.run(store)
        assert performed == 2 and refused == 0
        assert violations(store) == []

    def test_the_cap_holds_even_with_moves_left(self):
        descheduler = Descheduler(guard=Guard(), per_run_cap=1)
        store = sliver_city()
        performed, _ = descheduler.run(store)
        assert performed == 1

    def test_a_floor_refuses_and_the_move_is_reverted(self):
        guard = Guard(
            budgets=[
                Budget(
                    name="floor",
                    selector_key="app",
                    selector_value="web",
                    min_available=5,
                )
            ]
        )
        descheduler = Descheduler(guard=guard)
        store = sliver_city(labelled=True)
        homes_before = {t.spec.name: t.node for t in store.active_tasks()}
        performed, refused = descheduler.run(store)
        assert performed == 0 and refused == 1
        homes_after = {t.spec.name: t.node for t in store.active_tasks()}
        assert homes_before == homes_after
        assert "floor" in descheduler.refused[0]

    def test_the_record_names_who_refused(self):
        guard = Guard(
            budgets=[
                Budget(
                    name="web-floor",
                    selector_key="app",
                    selector_value="web",
                    min_available=5,
                )
            ]
        )
        descheduler = Descheduler(guard=guard)
        descheduler.run(sliver_city(labelled=True))
        assert descheduler.refused[0].startswith("t1: budget web-floor")

    def test_a_consolidated_city_needs_no_moves(self):
        descheduler = Descheduler(guard=Guard())
        store = sliver_city()
        descheduler.run(store)
        again = Descheduler(guard=Guard())
        performed, _ = again.run(store)
        assert performed == 0
