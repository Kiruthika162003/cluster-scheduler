from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.snapshot import dump
from fleet.store import Store
from fleet.whatif import rendered, what_if_add_nodes, what_if_lose_zone


def zoned_fleet() -> Store:
    store = Store()
    for number, zone in enumerate(["a", "a", "b"]):
        store.add_node(
            Node(
                name=f"n{number}",
                capacity=Resources(cpu=1000, memory=1000),
                labels={"zone": zone},
            )
        )
    task = Task(spec=TaskSpec(name="w", needs=Resources(cpu=600, memory=600)))
    task.bound_to("n0")
    store.add_task(task)
    return store


class TestWhatIf:
    def test_adding_nodes_moves_the_headroom(self):
        store = zoned_fleet()
        result = what_if_add_nodes(store, count=2, cpu=1000)
        assert result["before"]["headroom_cpu"] == 2400
        assert result["after"]["headroom_cpu"] == 4400
        assert result["after"]["nodes"] == 5

    def test_losing_a_zone_shows_the_risk(self):
        store = zoned_fleet()
        result = what_if_lose_zone(store, "a")
        assert result["before"]["n_plus_one"]
        assert result["after"]["headroom_cpu"] == 1000

    def test_the_live_store_is_never_touched(self):
        store = zoned_fleet()
        before = dump(store)
        what_if_add_nodes(store, count=3, cpu=500)
        what_if_lose_zone(store, "a")
        assert dump(store) == before

    def test_the_receipt_reads_before_after_delta(self):
        store = zoned_fleet()
        page = rendered(
            "we add two nodes", what_if_add_nodes(store, count=2, cpu=1000)
        )
        assert "nodes: 3 -> 5 (+2)" in page
        assert "headroom_cpu: 2400 -> 4400 (+2000)" in page

    def test_the_risk_transition_is_spelled_out(self):
        store = zoned_fleet()
        for number in range(1, 3):
            fat = Task(
                spec=TaskSpec(
                    name=f"fat{number}", needs=Resources(cpu=900, memory=900)
                )
            )
            fat.bound_to(f"n{number}")
            store.add_task(fat)
        page = rendered("we lose zone a", what_if_lose_zone(store, "a"))
        assert "-> AT RISK" in page or "AT RISK ->" in page
