"""The op fuzzer: random weather against the facade, invariants as the umpire.

A seeded stream of operator verbs, submits, deletes, scales, cordons,
drains, node joins and departures, steps, thrown at the Fleet facade
in random order, with the invariant suite consulted after every
operation. The fuzzer proves nothing about any single behaviour; what
it buys is the class of bug unit tests never meet, the interleaving
nobody thought to write, and it hands back the seed and the op index
of anything it finds, which turns a heisenbug into a regression test.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from fleet.api import Fleet
from fleet.control.budget import Budget
from fleet.control.deploy import DeploySpec
from fleet.errors import FleetError
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.verify import violations


@dataclass
class FuzzReport:
    seed: int
    ops_run: int
    op_log: list[str] = field(default_factory=list)
    failure: str | None = None

    def clean(self) -> bool:
        return self.failure is None


def _random_op(fleet: Fleet, source: random.Random, counter: int) -> str:
    roll = source.random()
    if roll < 0.30:
        name = f"task-{counter}"
        fleet.submit(
            "fuzz",
            Task(
                spec=TaskSpec(
                    name=name,
                    needs=Resources(
                        cpu=source.choice([100, 300, 600]),
                        memory=source.choice([100, 300, 600]),
                    ),
                    priority=source.choice([0, 10, 100, 1500]),
                )
            ),
        )
        return f"submit {name}"
    if roll < 0.40 and fleet.store.tasks:
        name = source.choice(sorted(fleet.store.tasks))
        fleet.delete("fuzz", name)
        return f"delete {name}"
    if roll < 0.50:
        name = f"auto-{counter}"
        fleet.store.add_node(
            Node(name=name, capacity=Resources(cpu=1000, memory=1000))
        )
        fleet.engine.queue.shape_changed(fleet.now)
        return f"join {name}"
    if roll < 0.58 and len(fleet.store.nodes) > 1:
        name = source.choice(sorted(fleet.store.nodes))
        moved = fleet.retire_node("fuzz", name)
        return f"retire {name} ({moved} moved)"
    if roll < 0.66 and fleet.store.nodes:
        name = source.choice(sorted(fleet.store.nodes))
        node = fleet.store.get_node(name)
        node.schedulable = not node.schedulable
        return f"toggle-cordon {name}"
    if roll < 0.74:
        spec = DeploySpec(
            name="churn",
            replicas=source.randrange(0, 6),
            template=TaskSpec(
                name="tpl", needs=Resources(cpu=200, memory=200)
            ),
        )
        fleet.apply_deploy("fuzz", spec)
        return f"scale churn={spec.replicas}"
    fleet.step()
    return "step"


def fuzz(seed: int, ops: int = 120) -> FuzzReport:
    source = random.Random(seed)
    fleet = Fleet()
    fleet.guard.budgets.append(
        Budget(
            name="churn-floor",
            selector_key="deploy",
            selector_value="churn",
            min_available=1,
        )
    )
    for number in range(2):
        fleet.store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    report = FuzzReport(seed=seed, ops_run=0)
    for counter in range(ops):
        try:
            line = _random_op(fleet, source, counter)
        except FleetError as refused:
            line = f"refused: {refused}"
        report.op_log.append(line)
        report.ops_run += 1
        broken = violations(fleet.store)
        if broken:
            report.failure = (
                f"seed {seed} op {counter} ({line}): {broken[0]}"
            )
            return report
    return report


def campaign(seeds: int, ops: int = 120) -> list[FuzzReport]:
    return [fuzz(seed, ops) for seed in range(seeds)]
