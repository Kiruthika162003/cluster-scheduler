"""A recurring fault against the fix budget: three repairs, then a human.

A fault reappears every ten ticks; the remediator holds a budget of
three fixes per fifty-tick window. It repairs the first three
occurrences and escalates the fourth with the budget's history behind
it, then resumes fixing once the window slides. The counters tell the
policy's whole story: seven occurrences over seventy ticks cost five
fixes and two escalations, and the escalations are the feature,
because a fault fixed five times an hour is being hidden, not fixed,
by the one system nobody is watching.
"""

from __future__ import annotations

from fleet.audit import Journal
from fleet.remediation import Remediator, Rule
from fleet.trials.verdict import Verdict


def run() -> Verdict:
    journal = Journal()
    standing_fault: list[str] = []

    def detect() -> list[str]:
        return list(standing_fault)

    def fix(finding: str) -> None:
        del finding
        standing_fault.clear()

    remediator = Remediator(
        journal=journal,
        budget_per_window=3,
        window=50,
        rules=[Rule(name="restart-flapper", detect=detect, fix=fix)],
    )

    occurrences = 0
    for now in range(70):
        if now % 10 == 0:
            standing_fault[:] = [f"flapper down at {now}"]
            occurrences += 1
        remediator.sweep(now)

    numbers = {
        "occurrences": occurrences,
        "fixed": remediator.fixed,
        "escalations": len(remediator.escalations),
        "journal_lines": len(journal.about("restart-flapper")),
    }
    holds = (
        occurrences == 7
        and remediator.fixed == 5
        and len(remediator.escalations) == 2
        and numbers["journal_lines"] == 7
    )
    return Verdict(
        trial="robotstop",
        sentence=(
            "the recurring fault is repaired three times, escalated on "
            "the fourth when the budget is spent, and repaired again once "
            "the window slides: five fixes and two escalations for seven "
            "occurrences, and the escalations are the feature"
        ),
        numbers=numbers,
        holds=holds,
    )
