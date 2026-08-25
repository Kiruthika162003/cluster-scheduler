from __future__ import annotations

from fleet.audit import Journal
from fleet.remediation import Remediator, Rule


def rig(budget: int = 2, window: int = 20) -> tuple[Remediator, list[str]]:
    standing: list[str] = []

    def detect() -> list[str]:
        return list(standing)

    def fix(finding: str) -> None:
        del finding
        standing.clear()

    remediator = Remediator(
        journal=Journal(),
        budget_per_window=budget,
        window=window,
        rules=[Rule(name="r", detect=detect, fix=fix)],
    )
    return remediator, standing


class TestFixing:
    def test_a_finding_inside_budget_is_fixed(self):
        remediator, standing = rig()
        standing.append("broken")
        told = remediator.sweep(now=0)
        assert told == ["[0] r fixed: broken"]
        assert standing == []

    def test_a_quiet_sweep_does_nothing(self):
        remediator, _ = rig()
        assert remediator.sweep(now=0) == []
        assert remediator.fixed == 0


class TestTheBudget:
    def test_past_the_budget_the_robot_escalates_once(self):
        remediator, standing = rig(budget=1, window=100)
        standing.append("broken")
        remediator.sweep(now=0)
        standing.append("broken again")
        first = remediator.sweep(now=1)
        second = remediator.sweep(now=2)
        assert "escalating" in first[0]
        assert second == []
        assert len(remediator.escalations) == 1

    def test_the_window_sliding_restores_the_budget(self):
        remediator, standing = rig(budget=1, window=10)
        standing.append("broken")
        remediator.sweep(now=0)
        standing.append("broken later")
        remediator.sweep(now=5)
        told = remediator.sweep(now=10)
        assert told == ["[10] r fixed: broken later"]

    def test_a_fixed_finding_may_escalate_again_if_it_returns(self):
        remediator, standing = rig(budget=1, window=10)
        standing.append("broken")
        remediator.sweep(now=0)
        standing.append("broken")
        remediator.sweep(now=1)
        remediator.sweep(now=10)
        standing.append("broken")
        remediator.sweep(now=11)
        assert len(remediator.escalations) == 2

    def test_every_action_reaches_the_journal(self):
        remediator, standing = rig(budget=1, window=100)
        standing.append("broken")
        remediator.sweep(now=0)
        standing.append("worse")
        remediator.sweep(now=1)
        story = remediator.journal.by("remediator")
        assert [decision.verb for decision in story] == ["fix", "escalate"]
