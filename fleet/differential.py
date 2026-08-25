"""Differential placement: two schedulers, one truth, any divergence is a bug.

The plain Scheduler and the queue-and-treaty Engine are meant to agree
whenever the engine's extra machinery has nothing to do: equal
priorities, no preemption, no benching. The differential harness runs
both against the same randomly shaped clusters and workloads and
demands identical placements task for task. Where they agree, the
engine's plumbing is provably inert at baseline; where they ever
disagree, one of them is wrong and the seed says which workload proves
it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.placement import Engine
from fleet.store import Store


@dataclass
class Divergence:
    seed: int
    task: str
    plain_home: str | None
    engine_home: str | None


@dataclass
class Differential:
    divergences: list[Divergence] = field(default_factory=list)
    runs: int = 0

    def _shape(self, seed: int) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
        source = random.Random(seed)
        nodes = [
            (f"n{number}", source.choice([600, 1000, 1500]))
            for number in range(source.randrange(2, 6))
        ]
        tasks = [
            (f"t{number}", source.choice([100, 250, 400]))
            for number in range(source.randrange(3, 12))
        ]
        return nodes, tasks

    def _place_plain(self, nodes, tasks) -> dict[str, str | None]:
        store = Store()
        for name, cpu in nodes:
            store.add_node(Node(name=name, capacity=Resources(cpu=cpu, memory=cpu)))
        scheduler = Scheduler()
        for name, cpu in tasks:
            store.add_task(
                Task(spec=TaskSpec(name=name, needs=Resources(cpu=cpu, memory=cpu)))
            )
        scheduler.schedule_pending(store)
        return {task.spec.name: task.node for task in store.tasks.values()}

    def _place_engine(self, nodes, tasks) -> dict[str, str | None]:
        store = Store()
        for name, cpu in nodes:
            store.add_node(Node(name=name, capacity=Resources(cpu=cpu, memory=cpu)))
        engine = Engine()
        for name, cpu in tasks:
            engine.submit(
                store,
                Task(spec=TaskSpec(name=name, needs=Resources(cpu=cpu, memory=cpu))),
            )
        engine.one_pass(store, now=0)
        return {task.spec.name: task.node for task in store.tasks.values()}

    def compare(self, seed: int) -> bool:
        nodes, tasks = self._shape(seed)
        plain = self._place_plain(nodes, tasks)
        engined = self._place_engine(nodes, tasks)
        self.runs += 1
        agreed = True
        for name in plain:
            if plain[name] != engined[name]:
                self.divergences.append(
                    Divergence(
                        seed=seed,
                        task=name,
                        plain_home=plain[name],
                        engine_home=engined[name],
                    )
                )
                agreed = False
        return agreed

    def campaign(self, seeds: int) -> int:
        for seed in range(seeds):
            self.compare(seed)
        return len(self.divergences)
