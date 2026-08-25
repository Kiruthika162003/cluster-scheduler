from __future__ import annotations

from fleet.fleetsummary import summary, top_tenants
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def billed_store() -> Store:
    store = Store()
    for number in range(3):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=2000, memory=2000))
        )
    for name, space, cpu, home in (
        ("s0", "search", 800, "n0"),
        ("s1", "search", 400, "n1"),
        ("a0", "ads", 700, "n1"),
        ("m0", "ml", 300, "n2"),
    ):
        task = Task(
            spec=TaskSpec(
                name=name, needs=Resources(cpu=cpu, memory=cpu), namespace=space
            )
        )
        task.bound_to(home)
        store.add_task(task)
    return store


class TestTopTenants:
    def test_tenants_rank_by_requested_cpu(self):
        told = top_tenants(billed_store())
        assert told == [("search", 1200), ("ads", 700), ("ml", 300)]

    def test_ties_break_by_name(self):
        store = Store()
        store.add_node(Node(name="n0", capacity=Resources(cpu=4000, memory=4000)))
        for name, space in (("b0", "beta"), ("a0", "alpha")):
            task = Task(
                spec=TaskSpec(
                    name=name, needs=Resources(cpu=100, memory=100), namespace=space
                )
            )
            task.bound_to("n0")
            store.add_task(task)
        assert top_tenants(store) == [("alpha", 100), ("beta", 100)]


class TestSummary:
    def test_the_page_reads_money_waste_who_risk(self):
        page = summary(
            billed_store(), usage={"s0": 500}, cpu_growth=0.02, memory_growth=0.01
        )
        order = [
            page.index("capacity"),
            page.index("waste:"),
            page.index("top tenants:"),
            page.index("n+1:"),
            page.index("growth:"),
        ]
        assert order == sorted(order)

    def test_the_numbers_come_from_the_modules(self):
        page = summary(
            billed_store(), usage={"s0": 500}, cpu_growth=0.02, memory_growth=0.01
        )
        assert "capacity 6000m cpu across 3 nodes" in page
        assert "requested 2200m, used 500m" in page
        assert "search: 1200m requested" in page

    def test_the_risk_line_speaks_when_it_matters(self):
        store = billed_store()
        fat = Task(
            spec=TaskSpec(
                name="fat", needs=Resources(cpu=1900, memory=1900), namespace="ml"
            )
        )
        fat.bound_to("n2")
        store.add_task(fat)
        page = summary(store, usage={}, cpu_growth=0.0, memory_growth=0.0)
        assert "AT RISK" in page
