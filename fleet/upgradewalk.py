"""The node upgrade walk: cordon, drain, patch, uncordon, one at a time.

Upgrading a kernel across the fleet is a rollout where the unit is a
node. The walk cordons one node so nothing new lands there, drains it
through the budget guard, waits for the drained tasks to land elsewhere,
patches, uncordons, and only then touches the next node. The meter that
certifies the walk is the truthful serving floor across the whole
campaign, and the surge node variant buys a higher floor with one spare
machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.control.budget import Guard
from fleet.objects import Node, Resources
from fleet.sim.cluster import Sim


@dataclass
class Walk:
    guard: Guard
    patched: list[str] = field(default_factory=list)
    cordoned: str | None = None
    floor_seen: int | None = None

    def _note_floor(self, sim: Sim) -> None:
        serving = sim.serving_count()
        if self.floor_seen is None or serving < self.floor_seen:
            self.floor_seen = serving

    def upgrade(self, sim: Sim, names: list[str], surge: Resources | None = None) -> None:
        if surge is not None:
            sim.store.add_node(Node(name="surge", capacity=surge))
            sim.monitor.beat(sim.store, "surge", sim.now)
        for name in names:
            node = sim.store.get_node(name)
            node.schedulable = False
            self.cordoned = name
            self._note_floor(sim)
            for _ in range(6):
                evicted, refused = self.guard.drain(sim.store, name)
                sim.tick()
                self._note_floor(sim)
                if not evicted and not refused:
                    break
            self.patched.append(name)
            node.schedulable = True
            self.cordoned = None
            sim.tick()
            self._note_floor(sim)
        if surge is not None:
            sim.store.get_node("surge").schedulable = False
            self.guard.drain(sim.store, "surge")
            sim.tick()
            leftovers = [
                task
                for task in sim.store.active_tasks()
                if task.node == "surge"
            ]
            if not leftovers:
                sim.store.remove_node("surge")
            self._note_floor(sim)
