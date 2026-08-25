"""The phase machine: which moves are legal, and which stories they tell.

Pending binds, Bound runs or comes back Pending, Running ends one of
three ways, and the terminal phases go nowhere. The table is the whole
module: every legal move with the story it tells, every illegal move a
refusal naming both ends. Controllers do not consult this at runtime,
the store stays fast and trusting; the table is for tests, invariants
and humans, which is where phase bugs are actually caught.
"""

from __future__ import annotations

import itertools

from fleet.errors import Invalid
from fleet.objects import PHASES

LEGAL_MOVES: dict[tuple[str, str], str] = {
    ("Pending", "Bound"): "the scheduler placed it",
    ("Bound", "Running"): "the probe came up",
    ("Bound", "Pending"): "its node died or it was displaced before starting",
    ("Bound", "Failed"): "it never started inside the startup budget",
    ("Bound", "Evicted"): "preemption took its slot before it started",
    ("Running", "Succeeded"): "it finished its work",
    ("Running", "Failed"): "it crashed past patience",
    ("Running", "Pending"): "its node died or it was evicted",
    ("Running", "Evicted"): "preemption took its slot",
    ("Evicted", "Pending"): "it requeued after displacement",
}


def may_move(before: str, after: str) -> bool:
    for phase in (before, after):
        if phase not in PHASES:
            raise Invalid(f"unknown phase {phase}")
    return (before, after) in LEGAL_MOVES


def story_of(before: str, after: str) -> str:
    if not may_move(before, after):
        raise Invalid(f"{before} -> {after} is not a legal move")
    return LEGAL_MOVES[(before, after)]


def terminal_phases() -> frozenset[str]:
    sources = {before for before, _ in LEGAL_MOVES}
    return frozenset(phase for phase in PHASES if phase not in sources)


def check_history(phases: list[str]) -> str | None:
    """The first illegal step in a task's recorded life, or None."""
    for before, after in itertools.pairwise(phases):
        if before == after:
            continue
        if not may_move(before, after):
            return f"{before} -> {after}"
    return None
