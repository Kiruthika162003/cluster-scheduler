"""The pressure loop: a node under pressure taints itself, grace does the rest.

QoS relief evicts inside one node's arithmetic; the pressure loop
makes the condition visible to the whole fleet: a node whose usage
crosses its capacity taints itself with the pressure key, graced
tenants get their notice through the taint evictor, and when relief
brings usage back under the line the taint lifts. The loop closes
what would otherwise be three disconnected mechanisms, and the
journal shows one story instead of three coincidences.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.audit import Journal
from fleet.sched.qos import PressureNode
from fleet.store import Store
from fleet.taintevict import TaintEvictor

PRESSURE_KEY = "pressure"


@dataclass
class PressureLoop:
    evictor: TaintEvictor
    journal: Journal
    tainted: set[str] = field(default_factory=set)

    def observe(
        self, store: Store, node: PressureNode, now: int
    ) -> list[str]:
        name = node.node.name
        actions = []
        if node.under_pressure() and name not in self.tainted:
            self.evictor.taint(name, PRESSURE_KEY, now)
            self.tainted.add(name)
            self.journal.note(
                now, "pressure-loop", name, "taint",
                f"usage {node.usage().cpu} over {node.node.capacity.cpu}",
            )
            actions.append(f"{name} tainted under pressure")
        elif not node.under_pressure() and name in self.tainted:
            self.evictor.untaint(name, PRESSURE_KEY)
            self.tainted.discard(name)
            self.journal.note(
                now, "pressure-loop", name, "untaint", "pressure relieved"
            )
            actions.append(f"{name} pressure lifted")
        evicted = self.evictor.sweep(store, now)
        for task_name in evicted:
            self.journal.note(
                now, "pressure-loop", task_name, "evict",
                f"grace expired under {PRESSURE_KEY}",
            )
            actions.append(f"{task_name} evicted after grace")
        return actions
