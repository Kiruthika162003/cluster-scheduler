"""The decision journal: what acted, on what, and the reason in words.

Controllers explain themselves or they cannot be operated. The journal
takes one line per decision, actor, subject, verb and reason, in the
order they happened, and answers the two questions an operator actually
asks: what happened to this object, and what did this controller do
recently. Nothing in the journal is derived state; it is testimony,
kept even when the object is long deleted.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Decision:
    tick: int
    actor: str
    subject: str
    verb: str
    reason: str

    def line(self) -> str:
        return f"[{self.tick}] {self.actor}: {self.verb} {self.subject}: {self.reason}"


@dataclass
class Journal:
    keep: int = 10000
    decisions: list[Decision] = field(default_factory=list)

    def note(self, tick: int, actor: str, subject: str, verb: str, reason: str) -> None:
        self.decisions.append(
            Decision(tick=tick, actor=actor, subject=subject, verb=verb, reason=reason)
        )
        while len(self.decisions) > self.keep:
            self.decisions.pop(0)

    def about(self, subject: str) -> list[Decision]:
        return [held for held in self.decisions if held.subject == subject]

    def by(self, actor: str, last: int = 20) -> list[Decision]:
        mine = [held for held in self.decisions if held.actor == actor]
        return mine[-last:]

    def story(self, subject: str) -> str:
        lines = [held.line() for held in self.about(subject)]
        return "\n".join(lines) if lines else f"nothing recorded about {subject}"
