from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.soft import Wish, blended, nodes_used, satisfaction, wish_scorer
from fleet.store import Store


def node(name: str, disk: str, cpu: int = 1000) -> Node:
    return Node(
        name=name, capacity=Resources(cpu=cpu, memory=cpu), labels={"disk": disk}
    )


def task(name: str = "t") -> Task:
    return Task(spec=TaskSpec(name=name, needs=Resources(cpu=100, memory=100)))


WISHES = (Wish(label="disk", value="ssd", weight=2.0),)


class TestWishScorer:
    def test_a_granted_wish_earns_its_weight(self):
        score = wish_scorer(WISHES)
        assert score(task(), node("a", "ssd"), []) == 2.0
        assert score(task(), node("b", "hdd"), []) == 0.0

    def test_wishes_add_up(self):
        wishes = (
            Wish(label="disk", value="ssd", weight=2.0),
            Wish(label="zone", value="a", weight=1.0),
        )
        rich = Node(
            name="n",
            capacity=Resources(cpu=1, memory=1),
            labels={"disk": "ssd", "zone": "a"},
        )
        assert wish_scorer(wishes)(task(), rich, []) == 3.0

    def test_blended_mixes_fullness_and_wishes(self):
        tenant = task("tenant")
        tenant.bound_to("full-hdd")
        full_hdd = node("full-hdd", "hdd", cpu=200)
        empty_ssd = node("empty-ssd", "ssd")
        score = blended(WISHES, preference_weight=1.0)
        assert score(task("x"), empty_ssd, [tenant]) > score(
            task("x"), full_hdd, [tenant]
        )


class TestMeters:
    def happy_store(self) -> Store:
        store = Store()
        store.add_node(node("ssd-0", "ssd"))
        store.add_node(node("hdd-0", "hdd"))
        first = task("a")
        first.bound_to("ssd-0")
        store.add_task(first)
        second = task("b")
        second.bound_to("hdd-0")
        store.add_task(second)
        return store

    def test_satisfaction_is_the_happy_share(self):
        assert satisfaction(self.happy_store(), WISHES) == 0.5

    def test_an_empty_store_is_unsatisfied(self):
        assert satisfaction(Store(), WISHES) == 0.0

    def test_nodes_used_counts_distinct_homes(self):
        assert nodes_used(self.happy_store()) == 2
