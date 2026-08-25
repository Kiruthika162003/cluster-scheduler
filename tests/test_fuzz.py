from __future__ import annotations

from fleet.api import Fleet
from fleet.control.budget import Budget
from fleet.fuzz import campaign, fuzz
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.verify import violations


class TestRetire:
    def guarded_fleet(self) -> Fleet:
        fleet = Fleet()
        for number in range(2):
            fleet.store.add_node(
                Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
            )
        fleet.guard.budgets.append(
            Budget(
                name="floor",
                selector_key="app",
                selector_value="web",
                min_available=2,
            )
        )
        for number in range(2):
            fleet.submit(
                "k",
                Task(
                    spec=TaskSpec(
                        name=f"w{number}",
                        needs=Resources(cpu=300, memory=300),
                        labels=(("app", "web"),),
                    )
                ),
            )
        fleet.step()
        return fleet

    def test_retire_leaves_no_corpses_behind_a_budget(self):
        fleet = self.guarded_fleet()
        moved = fleet.retire_node("k", "n0")
        assert moved == 2
        assert "n0" not in fleet.store.nodes
        assert violations(fleet.store) == []

    def test_the_stragglers_land_again(self):
        fleet = self.guarded_fleet()
        fleet.retire_node("k", "n0")
        fleet.step()
        homes = {task.node for task in fleet.store.active_tasks()}
        assert homes == {"n1"}

    def test_the_journal_admits_the_bypass(self):
        fleet = self.guarded_fleet()
        fleet.retire_node("k", "n0")
        story = fleet.journal.story("n0")
        assert "budget-protected tasks requeued anyway" in story


class TestFuzz:
    def test_a_seed_replays_identically(self):
        one = fuzz(seed=7, ops=80)
        two = fuzz(seed=7, ops=80)
        assert one.op_log == two.op_log

    def test_the_campaign_is_clean(self):
        reports = campaign(seeds=15, ops=100)
        assert all(report.clean() for report in reports)

    def test_a_report_counts_its_ops(self):
        report = fuzz(seed=3, ops=50)
        assert report.ops_run == 50
        assert len(report.op_log) == 50
