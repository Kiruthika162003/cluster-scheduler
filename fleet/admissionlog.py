"""The admission log: every refusal a task ever heard, in one place.

A task refused by quota at 9:02, by the hook chain at 9:15 after the
quota was raised, and by the fits filter at 9:20 after the labels
were fixed has told three different people three different stories.
The log threads them: every gate that refuses records its verdict
under the task's name with the tick and the gate, so the owner reads
one timeline instead of three dashboards. The summary counts
refusals by gate across all tasks, which is the platform's own
report card: the gate that refuses the most is either doing its job
or misconfigured, and the ratio of its refusals to its reversals
says which.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Refusal:
    tick: int
    task: str
    gate: str
    reason: str


@dataclass
class AdmissionLog:
    refusals: list[Refusal] = field(default_factory=list)
    admitted: dict[str, int] = field(default_factory=dict)

    def refuse(self, tick: int, task: str, gate: str, reason: str) -> None:
        self.refusals.append(
            Refusal(tick=tick, task=task, gate=gate, reason=reason)
        )

    def admit(self, tick: int, task: str) -> None:
        self.admitted[task] = tick

    def timeline(self, task: str) -> str:
        rows = [
            refusal
            for refusal in self.refusals
            if refusal.task == task
        ]
        if not rows and task not in self.admitted:
            return f"{task}: never seen"
        lines = [f"{task}:"]
        for refusal in rows:
            lines.append(
                f"  [{refusal.tick}] refused by {refusal.gate}: "
                f"{refusal.reason}"
            )
        if task in self.admitted:
            lines.append(f"  [{self.admitted[task]}] admitted")
        else:
            lines.append("  still outside")
        return "\n".join(lines)

    def by_gate(self) -> dict[str, dict[str, int]]:
        """Per gate: refusals issued, and how many were later reversed
        (the task was ultimately admitted)."""
        book: dict[str, dict[str, int]] = {}
        for refusal in self.refusals:
            row = book.setdefault(refusal.gate, {"refusals": 0, "reversed": 0})
            row["refusals"] += 1
            admitted_at = self.admitted.get(refusal.task)
            if admitted_at is not None and admitted_at > refusal.tick:
                row["reversed"] += 1
        return book

    def report_card(self) -> str:
        book = self.by_gate()
        if not book:
            return "no refusals recorded"
        lines = []
        for gate in sorted(book, key=lambda g: -book[g]["refusals"]):
            row = book[gate]
            rate = row["reversed"] / row["refusals"]
            judgement = (
                "mostly reversed: check its configuration"
                if rate > 0.5
                else "mostly final: doing its job"
            )
            lines.append(
                f"{gate}: {row['refusals']} refusals, "
                f"{row['reversed']} reversed ({judgement})"
            )
        return "\n".join(lines)
