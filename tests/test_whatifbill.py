from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.snapshot import dump
from fleet.store import Store
from fleet.whatifbill import price_expansion, receipt


def rented_fleet() -> tuple[Store, dict[str, int]]:
    store = Store()
    hourly = {}
    for number in range(2):
        name = f"n{number}"
        store.add_node(
            Node(name=name, capacity=Resources(cpu=1000, memory=1000))
        )
        hourly[name] = 10
    task = Task(spec=TaskSpec(name="w", needs=Resources(cpu=600, memory=600)))
    task.bound_to("n0")
    store.add_task(task)
    return store, hourly


class TestPricing:
    def test_the_two_options_compare_by_one_ratio(self):
        store, hourly = rented_fleet()
        small = price_expansion(store, hourly, count=4, cpu=1000, node_hourly=10)
        big = price_expansion(store, hourly, count=1, cpu=4000, node_hourly=32)
        assert small["headroom_per_hourly_unit"] == 100.0
        assert big["headroom_per_hourly_unit"] == 125.0

    def test_headroom_moves_by_the_added_capacity(self):
        store, hourly = rented_fleet()
        result = price_expansion(store, hourly, count=2, cpu=1000, node_hourly=10)
        assert result["headroom_after"] - result["headroom_before"] == 2000

    def test_empty_nodes_do_not_inflate_the_current_bill(self):
        store, hourly = rented_fleet()
        result = price_expansion(store, hourly, count=3, cpu=1000, node_hourly=10)
        assert result["bill_after"] == result["bill_before"]
        assert result["added_rent_if_occupied"] == 3 * 10 * 720

    def test_the_live_store_is_untouched(self):
        store, hourly = rented_fleet()
        before = dump(store)
        price_expansion(store, hourly, count=5, cpu=1000, node_hourly=10)
        assert dump(store) == before


class TestReceipt:
    def test_the_receipt_reads_both_currencies(self):
        store, hourly = rented_fleet()
        result = price_expansion(store, hourly, count=2, cpu=1000, node_hourly=10)
        page = receipt("we add two mediums", result)
        assert "headroom: 1400m -> 3400m" in page
        assert "up to 14400 more" in page
