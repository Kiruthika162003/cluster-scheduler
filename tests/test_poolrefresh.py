from __future__ import annotations

from fleet.api import Fleet
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.poolrefresh import PoolRefresh, RefreshLedger
from fleet.verify import violations


def loaded_fleet() -> Fleet:
    fleet = Fleet()
    for number in range(3):
        fleet.store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    for number in range(4):
        fleet.submit(
            "setup",
            Task(
                spec=TaskSpec(
                    name=f"w{number}", needs=Resources(cpu=400, memory=400)
                )
            ),
        )
    fleet.step()
    return fleet


class TestRefresh:
    def test_the_whole_pool_is_replaced(self):
        fleet = loaded_fleet()
        ledger = RefreshLedger(pool=["n0", "n1", "n2"])
        steps = PoolRefresh().run(fleet, "oncall", ledger)
        assert ledger.done() and steps == 3
        assert sorted(fleet.store.nodes) == [
            "n0-replacement", "n1-replacement", "n2-replacement",
        ]

    def test_capacity_never_dips_and_nothing_breaks(self):
        fleet = loaded_fleet()
        ledger = RefreshLedger(pool=["n0", "n1", "n2"])
        refresh = PoolRefresh()
        while not ledger.done():
            assert len(fleet.store.nodes) >= 3
            refresh.step(fleet, "oncall", ledger)
            assert violations(fleet.store) == []

    def test_every_task_survives_the_refresh(self):
        fleet = loaded_fleet()
        ledger = RefreshLedger(pool=["n0", "n1", "n2"])
        PoolRefresh().run(fleet, "oncall", ledger)
        for _ in range(3):
            fleet.step()
        assert sum(1 for t in fleet.store.tasks.values() if t.is_active()) == 4

    def test_an_interrupted_refresh_resumes_by_name(self):
        fleet = loaded_fleet()
        ledger = RefreshLedger(pool=["n0", "n1", "n2"])
        refresh = PoolRefresh()
        refresh.step(fleet, "oncall", ledger)
        resumed = PoolRefresh()
        steps = resumed.run(fleet, "oncall", ledger)
        assert steps == 2
        assert ledger.done()

    def test_a_departed_node_is_skipped_not_failed(self):
        fleet = loaded_fleet()
        fleet.retire_node("someone", "n1")
        ledger = RefreshLedger(pool=["n0", "n1", "n2"])
        PoolRefresh().run(fleet, "oncall", ledger)
        assert "n1 already gone, skipped" in ledger.log
        assert ledger.done()
