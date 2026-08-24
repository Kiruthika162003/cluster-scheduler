"""A trial is an experiment with its conclusion attached to its numbers.

Each trial module exposes run() returning a Verdict: the sentence the
experiment supports, the measurements behind it, and whether the checks
that make the sentence true still pass. A verdict whose checks fail is
kept, not hidden, because a broken expectation is the most informative
thing a test suite produces.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Verdict:
    trial: str
    sentence: str
    numbers: dict = field(default_factory=dict)
    holds: bool = True

    def line(self) -> str:
        mark = "holds" if self.holds else "BROKEN"
        shown = ", ".join(f"{key}={value}" for key, value in sorted(self.numbers.items()))
        return f"{self.trial}: {self.sentence} [{mark}] ({shown})"
