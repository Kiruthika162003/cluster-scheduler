"""Label selectors: a tiny query language with no surprises in it.

A selector is a comma-separated list of clauses: key=value demands,
key!=value forbids, and a bare key demands presence. Clauses AND
together; there is no OR, no precedence, no escaping, because every
selector bug in the wild is someone discovering their query language
had more features than their mental model. The parser refuses what it
does not understand rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleet.errors import Invalid
from fleet.objects import Task
from fleet.store import Store


@dataclass(frozen=True)
class Clause:
    key: str
    op: str
    value: str

    def matches(self, labels: dict[str, str]) -> bool:
        if self.op == "present":
            return self.key in labels
        if self.op == "=":
            return labels.get(self.key) == self.value
        return labels.get(self.key) != self.value


def parse(text: str) -> tuple[Clause, ...]:
    clauses = []
    for raw in text.split(","):
        piece = raw.strip()
        if not piece:
            raise Invalid("empty clause in selector")
        if "!=" in piece:
            key, value = piece.split("!=", 1)
            op = "!="
        elif "=" in piece:
            key, value = piece.split("=", 1)
            op = "="
        else:
            key, value, op = piece, "", "present"
        key = key.strip()
        value = value.strip()
        if not key:
            raise Invalid(f"clause {piece!r} has no key")
        if op != "present" and not value:
            raise Invalid(f"clause {piece!r} has no value")
        clauses.append(Clause(key=key, op=op, value=value))
    return tuple(clauses)


def matches(clauses: tuple[Clause, ...], labels: dict[str, str]) -> bool:
    return all(clause.matches(labels) for clause in clauses)


def select(store: Store, text: str) -> list[Task]:
    clauses = parse(text)
    return sorted(
        (
            task
            for task in store.tasks.values()
            if matches(clauses, task.spec.label_map())
        ),
        key=lambda task: task.spec.name,
    )
