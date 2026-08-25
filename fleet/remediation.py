"""Auto-remediation with a budget: the robot fixes, then the robot stops.

A rule binds a detector to a fix. The engine runs detectors, applies
fixes, and spends from a remediation budget per window; past the
budget it pages instead of fixing, because a fault that needs fixing
five times an hour is not being fixed, it is being hidden, and the
automation that hides it is the one system nobody is watching. Every
fix and every escalation is journalled with the rule's name.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from fleet.audit import Journal


@dataclass(frozen=True)
class Rule:
    name: str
    detect: Callable[[], list[str]]
    fix: Callable[[str], None]


@dataclass
class Remediator:
    journal: Journal
    budget_per_window: int = 3
    window: int = 50
    rules: list[Rule] = field(default_factory=list)
    spent: dict[str, list[int]] = field(default_factory=dict)
    fixed: int = 0
    escalations: list[str] = field(default_factory=list)
    escalated_findings: set[tuple[str, str]] = field(default_factory=set)

    def _budget_left(self, rule: Rule, now: int) -> int:
        history = [
            tick
            for tick in self.spent.get(rule.name, [])
            if now - tick < self.window
        ]
        self.spent[rule.name] = history
        return self.budget_per_window - len(history)

    def sweep(self, now: int) -> list[str]:
        actions = []
        for rule in self.rules:
            findings = rule.detect()
            for finding in findings:
                if self._budget_left(rule, now) <= 0:
                    key = (rule.name, finding)
                    if key not in self.escalated_findings:
                        self.escalated_findings.add(key)
                        page = (
                            f"[{now}] {rule.name} exhausted its budget, "
                            f"escalating: {finding}"
                        )
                        self.escalations.append(page)
                        self.journal.note(
                            now, "remediator", rule.name, "escalate", finding
                        )
                        actions.append(page)
                    continue
                rule.fix(finding)
                self.escalated_findings.discard((rule.name, finding))
                self.spent.setdefault(rule.name, []).append(now)
                self.fixed += 1
                self.journal.note(
                    now, "remediator", rule.name, "fix", finding
                )
                actions.append(f"[{now}] {rule.name} fixed: {finding}")
        return actions
