from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store
from fleet.utilization import rendered, survey, totals


def measured_store() -> tuple[Store, dict[str, int]]:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    store.add_node(Node(name="n1", capacity=Resources(cpu=1000, memory=1000)))
    fat = Task(spec=TaskSpec(name="fat", needs=Resources(cpu=600, memory=100)))
    fat.bound_to("n0")
    store.add_task(fat)
    lean = Task(spec=TaskSpec(name="lean", needs=Resources(cpu=200, memory=100)))
    lean.bound_to("n0")
    store.add_task(lean)
    return store, {"fat": 150, "lean": 180}


class TestSurvey:
    def test_the_two_gaps_are_separated(self):
        store, usage = measured_store()
        rows = survey(store, usage)
        n0 = rows[0]
        assert n0.requested == 800 and n0.used == 330
        assert n0.request_gap() == 470
        assert n0.allocation_gap() == 200

    def test_an_empty_node_is_pure_allocation_gap(self):
        store, usage = measured_store()
        n1 = survey(store, usage)[1]
        assert n1.request_gap() == 0
        assert n1.allocation_gap() == 1000

    def test_unmeasured_tasks_count_as_using_nothing(self):
        store, _ = measured_store()
        rows = survey(store, {})
        assert rows[0].used == 0

    def test_totals_add_across_nodes(self):
        store, usage = measured_store()
        whole = totals(survey(store, usage))
        assert whole == {
            "capacity": 2000,
            "requested": 800,
            "used": 330,
            "request_gap": 470,
            "allocation_gap": 1200,
        }


class TestRender:
    def test_the_page_names_both_owners(self):
        store, usage = measured_store()
        page = rendered(store, usage)
        assert "teams waste 24%" in page
        assert "the platform strands 60%" in page
