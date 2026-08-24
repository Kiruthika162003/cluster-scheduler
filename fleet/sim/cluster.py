"""The cluster in a loop: every controller takes its turn, time is a tick.

The simulation wires the store, the scheduler, the node monitor, the
health keeper and the deployment controller into one deterministic loop.
A script says which nodes fall silent when and which probes fail; the
sim only turns the crank. Everything interesting is read off the
components' own meters afterwards, which keeps the harness from having
opinions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.autoscale import NodeScaler
from fleet.control.deploy import Deployer, DeploySpec
from fleet.control.health import Keeper
from fleet.control.nodes import Monitor
from fleet.objects import Node, Resources
from fleet.sched.core import Scheduler
from fleet.sched.scorers import spread
from fleet.store import Store


@dataclass
class Script:
    """Ticks during which each named node is silent."""

    silences: dict[str, tuple[int, int]] = field(default_factory=dict)

    def is_silent(self, node_name: str, now: int) -> bool:
        window = self.silences.get(node_name)
        return window is not None and window[0] <= now < window[1]


@dataclass
class Sim:
    store: Store = field(default_factory=Store)
    scheduler: Scheduler = field(default_factory=lambda: Scheduler(scorers=(spread,)))
    monitor: Monitor = field(default_factory=Monitor)
    keeper: Keeper = field(default_factory=Keeper)
    deployer: Deployer = field(default_factory=Deployer)
    deploys: list[DeploySpec] = field(default_factory=list)
    script: Script = field(default_factory=Script)
    node_scaler: NodeScaler | None = None
    auto_node_shape: Resources = field(
        default_factory=lambda: Resources(cpu=1000, memory=1000)
    )
    now: int = 0
    availability: list[int] = field(default_factory=list)
    serving_history: list[int] = field(default_factory=list)
    stuck_history: list[int] = field(default_factory=list)

    def add_nodes(self, count: int, cpu: int = 1000, memory: int = 1000) -> None:
        for number in range(count):
            self.store.add_node(
                Node(name=f"n{number}", capacity=Resources(cpu=cpu, memory=memory))
            )

    def running_count(self) -> int:
        return sum(1 for task in self.store.tasks.values() if task.phase == "Running")

    def serving_count(self) -> int:
        """Running tasks whose node is actually ready: no ghosts counted."""
        return sum(
            1
            for task in self.store.tasks.values()
            if task.phase == "Running"
            and task.node is not None
            and self.store.nodes.get(task.node) is not None
            and self.store.nodes[task.node].ready
        )

    def tick(self) -> None:
        for name in self.store.nodes:
            if not self.script.is_silent(name, self.now):
                self.monitor.beat(self.store, name, self.now)
        self.monitor.sweep(self.store, self.now)
        for spec in self.deploys:
            self.deployer.reconcile(self.store, spec)
        _, stuck = self.scheduler.schedule_pending(self.store)
        self.stuck_history.append(stuck)
        if self.node_scaler is not None:
            for name in self.node_scaler.observe_stuck(stuck, self.now):
                self.store.add_node(
                    Node(name=name, capacity=self.auto_node_shape)
                )
                self.monitor.beat(self.store, name, self.now)
            empty = [
                node.name
                for node in self.store.nodes.values()
                if node.name.startswith("auto-")
                and not any(
                    task.node == node.name for task in self.store.active_tasks()
                )
            ]
            for name in self.node_scaler.observe_empty(empty, self.now):
                self.store.remove_node(name)
        self.keeper.tick(self.store, self.now)
        self.availability.append(self.running_count())
        self.serving_history.append(self.serving_count())
        self.now += 1

    def run(self, ticks: int) -> None:
        for _ in range(ticks):
            self.tick()

    def worst_availability(self, since: int = 0) -> int:
        return min(self.availability[since:], default=0)

    def worst_serving(self, since: int = 0) -> int:
        return min(self.serving_history[since:], default=0)
