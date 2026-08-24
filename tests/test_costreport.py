from __future__ import annotations

from fleet.costreport import rendered, split_bill
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def billed_store() -> tuple[Store, dict[str, int]]:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    store.add_node(Node(name="n1", capacity=Resources(cpu=1000, memory=1000)))
    a = Task(
        spec=TaskSpec(name="a", needs=Resources(cpu=600, memory=100), namespace="search")
    )
    a.bound_to("n0")
    store.add_task(a)
    b = Task(
        spec=TaskSpec(name="b", needs=Resources(cpu=200, memory=100), namespace="ads")
    )
    b.bound_to("n0")
    store.add_task(b)
    return store, {"n0": 10, "n1": 10}


class TestSplit:
    def test_the_split_follows_requested_share(self):
        store, hourly = billed_store()
        lines, _ = split_bill(store, hourly, hours=1)
        by_space = {line.namespace: line.charge for line in lines}
        assert by_space == {"search": 6.0, "ads": 2.0}

    def test_the_idle_rump_goes_to_the_platform(self):
        store, hourly = billed_store()
        _, idle = split_bill(store, hourly, hours=1)
        assert idle == 2.0

    def test_an_empty_node_is_not_billed_at_all(self):
        store, hourly = billed_store()
        lines, idle = split_bill(store, hourly, hours=1)
        total = sum(line.charge for line in lines) + idle
        assert total == 10.0

    def test_hours_scale_the_bill(self):
        store, hourly = billed_store()
        lines_day, idle_day = split_bill(store, hourly, hours=24)
        assert idle_day == 48.0
        assert lines_day[0].charge in (48.0, 144.0)

    def test_shares_sum_to_one(self):
        store, hourly = billed_store()
        lines, idle = split_bill(store, hourly, hours=1)
        total = sum(line.charge for line in lines) + idle
        shares = [line.charge / total for line in lines] + [idle / total]
        assert abs(sum(shares) - 1.0) < 1e-9


class TestRender:
    def test_the_page_ends_with_the_platform_line(self):
        store, hourly = billed_store()
        page = rendered(store, hourly, hours=1)
        assert page.strip().endswith("platform-idle 2.0")
        assert "search" in page and "ads" in page
