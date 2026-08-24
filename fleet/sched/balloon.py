"""Headroom balloons: the burst pops them instead of production.

Preemption already makes a critical burst land immediately; the open
question is who pays. Without balloons the victims are production
tasks, evicted mid-flight and requeued behind a node warmup. Balloons
are scavenger-class placeholders that get benched when the cluster is
full, which makes them a standing demand signal: the autoscaler
provisions for them ahead of the burst, they inflate onto the new
capacity, and when the burst arrives the treaty picks them as the
cheapest victims. Same burst latency, different casualty list.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.objects import Resources, Task, TaskSpec
from fleet.sched.placement import Engine
from fleet.store import Store


@dataclass
class BalloonFleet:
    shape: Resources
    count: int
    names: list[str] = field(default_factory=list)

    def submit(self, store: Store, engine: Engine) -> None:
        for number in range(self.count):
            name = f"balloon-{number}"
            engine.submit(
                store,
                Task(
                    spec=TaskSpec(
                        name=name,
                        needs=self.shape,
                        priority=0,
                        labels=(("balloon", "true"),),
                    )
                ),
            )
            self.names.append(name)

    def inflated(self, store: Store) -> int:
        return sum(
            1
            for name in self.names
            if name in store.tasks and store.tasks[name].is_active()
        )

    def popped_ever(self, engine: Engine) -> int:
        return sum(
            1
            for decision in engine.journal.decisions
            if decision.verb == "displace" and decision.subject in self.names
        )
