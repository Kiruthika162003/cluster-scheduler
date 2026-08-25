"""Why this node: the scoring table an operator can argue with.

The scheduler's choice is a max over sums, which is exactly as opaque
as it sounds when a task lands somewhere surprising. The explainer
reruns the decision with the ledger open: every candidate node, every
filter's verdict, every scorer's contribution, and the total, sorted
the way the scheduler sorted. The table is the difference between the
scheduler was wrong and the spread scorer outvoted the packer by 0.2,
which are different conversations.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from fleet.objects import Node, Task
from fleet.sched.core import Scheduler
from fleet.store import Store


@dataclass(frozen=True)
class Candidacy:
    node: str
    refusal: str | None
    scores: tuple[tuple[str, float], ...]

    def total(self) -> float:
        return sum(value for _, value in self.scores)


@dataclass
class Explanation:
    task: str
    candidacies: list[Candidacy] = field(default_factory=list)

    def chosen(self) -> str | None:
        passing = [held for held in self.candidacies if held.refusal is None]
        if not passing:
            return None
        best = max(
            sorted(passing, key=lambda held: held.node),
            key=lambda held: held.total(),
        )
        return best.node

    def table(self) -> str:
        out = io.StringIO()
        out.write(f"placement of {self.task}\n")
        for held in self.candidacies:
            if held.refusal is not None:
                out.write(f"  {held.node}: refused, {held.refusal}\n")
                continue
            parts = "  ".join(
                f"{name}={value:.3f}" for name, value in held.scores
            )
            marker = " <- chosen" if held.node == self.chosen() else ""
            out.write(
                f"  {held.node}: total={held.total():.3f}  {parts}{marker}\n"
            )
        return out.getvalue()


def explain(scheduler: Scheduler, store: Store, task: Task) -> Explanation:
    explanation = Explanation(task=task.spec.name)
    active = store.active_tasks()
    for name in sorted(store.nodes):
        node: Node = store.nodes[name]
        refusal = None
        for check in scheduler.filters:
            refusal = check(task, node, active)
            if refusal is not None:
                break
        if refusal is not None:
            explanation.candidacies.append(
                Candidacy(node=name, refusal=refusal, scores=())
            )
            continue
        scores = tuple(
            (scorer.__name__, scorer(task, node, active))
            for scorer in scheduler.scorers
        )
        explanation.candidacies.append(
            Candidacy(node=name, refusal=None, scores=scores)
        )
    return explanation
