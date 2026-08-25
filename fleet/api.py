"""The operator facade: the eight verbs, each one journalled.

Every operation an operator actually types, submit, delete, scale,
cordon, uncordon, drain, pause, resume, behind one object that owns
the wiring: the store, the engine, the guard, the journal. The facade
adds no policy of its own; its whole job is that every verb lands in
the journal with who asked, and that there is exactly one spelling of
each operation in the codebase instead of five slightly different
inline versions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.audit import Journal
from fleet.control.budget import Guard
from fleet.control.deploy import Deployer, DeploySpec
from fleet.errors import NotFound
from fleet.objects import Task
from fleet.sched.placement import Engine
from fleet.store import Store


@dataclass
class Fleet:
    store: Store = field(default_factory=Store)
    engine: Engine = field(default_factory=Engine)
    deployer: Deployer = field(default_factory=Deployer)
    guard: Guard = field(default_factory=Guard)
    journal: Journal = field(default_factory=Journal)
    deploys: dict[str, DeploySpec] = field(default_factory=dict)
    now: int = 0

    def _note(self, who: str, subject: str, verb: str, reason: str) -> None:
        self.journal.note(self.now, who, subject, verb, reason)

    def submit(self, who: str, task: Task) -> None:
        self.engine.submit(self.store, task)
        self._note(who, task.spec.name, "submit", "accepted into the queue")

    def delete(self, who: str, name: str) -> None:
        if name not in self.store.tasks:
            raise NotFound(f"task {name}")
        self.store.remove_task(name)
        self.engine.queue.forget(name)
        self._note(who, name, "delete", "removed at request")

    def apply_deploy(self, who: str, spec: DeploySpec) -> None:
        self.deploys[spec.name] = spec
        created, deleted = self.deployer.reconcile(self.store, spec)
        for task in self.store.pending_tasks():
            if task.spec.label_map().get("deploy") == spec.name:
                self.engine.queue.offer(
                    task.spec.name, task.spec.priority, task.spec.namespace
                )
        self._note(
            who,
            spec.name,
            "apply",
            f"replicas {spec.replicas}: created {created}, deleted {deleted}",
        )

    def scale(self, who: str, deploy_name: str, replicas: int) -> None:
        held = self.deploys.get(deploy_name)
        if held is None:
            raise NotFound(f"deploy {deploy_name}")
        spec = DeploySpec(
            name=held.name, replicas=replicas, template=held.template
        )
        self.apply_deploy(who, spec)

    def cordon(self, who: str, node_name: str) -> None:
        node = self.store.get_node(node_name)
        node.schedulable = False
        self._note(who, node_name, "cordon", "no new work will land here")

    def uncordon(self, who: str, node_name: str) -> None:
        node = self.store.get_node(node_name)
        node.schedulable = True
        self._note(who, node_name, "uncordon", "open for placement again")

    def drain(self, who: str, node_name: str) -> tuple[list[str], list[str]]:
        self.cordon(who, node_name)
        evicted, refused = self.guard.drain(self.store, node_name)
        for name in evicted:
            self.engine.queue.offer(
                name, self.store.get_task(name).spec.priority
            )
        self._note(
            who,
            node_name,
            "drain",
            f"evicted {len(evicted)}, refused {len(refused)} by budget",
        )
        return evicted, refused


    def retire_node(self, who: str, node_name: str) -> int:
        """Remove a node for good: drain what budgets allow, requeue the rest.

        Departure is involuntary for whatever is still aboard, so the
        stragglers bypass the budgets the way a node death would, and the
        journal says so instead of pretending the drain sufficed.
        """
        evicted, refused = self.drain(who, node_name)
        for name in refused:
            task = self.store.get_task(name)
            generation = task.generation
            task.phase = "Pending"
            task.node = None
            store_task = task
            self.store.update_task(store_task, read_generation=generation)
            self.engine.queue.offer(
                name, task.spec.priority, task.spec.namespace
            )
        self.store.remove_node(node_name)
        self.engine.queue.shape_changed(self.now)
        self._note(
            who,
            node_name,
            "retire",
            f"gone; {len(refused)} budget-protected tasks requeued anyway",
        )
        return len(evicted) + len(refused)

    def step(self) -> tuple[int, int]:
        placed, benched = self.engine.one_pass(self.store, self.now)
        self.now += 1
        return placed, benched
