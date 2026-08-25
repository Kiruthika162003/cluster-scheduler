"""Probes and the crashloop ladder: failures restart, restarts slow down.

A bound task starts, a probe says whether it came up, and a failed probe
restarts it. Each restart doubles the wait before the next attempt up to
a ceiling, and a run of clean ticks pays the ladder back down. The
ladder is the difference between a task that crashes hourly and a task
that takes its node hostage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.store import Store

BACKOFF_BASE = 2
BACKOFF_CAP = 32
FORGIVE_AFTER = 20


@dataclass
class Probe:
    """Deterministic script: fails the attempts listed, passes the rest."""

    failing_attempts: frozenset[int] = frozenset()

    def up(self, attempt: int) -> bool:
        return attempt not in self.failing_attempts


@dataclass
class StartupGate:
    """Liveness is suspended until the task first comes up, within a budget.

    The gate answers one question per task: has it ever been up. Until
    then, liveness failures are absorbed against the startup budget; a
    task that exhausts the budget without ever coming up is declared
    Failed outright rather than crashlooped, because a service that has
    never once started is not sick, it is broken.
    """

    budget: int
    absorbed: dict[str, int] = None
    started: set[str] = None
    broken: set[str] = None

    def __post_init__(self) -> None:
        if self.absorbed is None:
            self.absorbed = {}
        if self.started is None:
            self.started = set()
        if self.broken is None:
            self.broken = set()

    def admit_failure(self, task_name: str) -> str:
        """Returns absorb, or broken when the budget is spent."""
        if task_name in self.started:
            return "restart"
        spent = self.absorbed.get(task_name, 0) + 1
        self.absorbed[task_name] = spent
        if spent >= self.budget:
            self.broken.add(task_name)
            return "broken"
        return "absorb"

    def note_up(self, task_name: str) -> None:
        self.started.add(task_name)


@dataclass
class Keeper:
    probes: dict[str, Probe] = field(default_factory=dict)
    startup_gate: StartupGate | None = None
    waiting_until: dict[str, int] = field(default_factory=dict)
    last_healthy: dict[str, int] = field(default_factory=dict)
    restarts: int = 0
    forgiven: int = 0

    def backoff_for(self, restarts: int) -> int:
        return min(BACKOFF_CAP, BACKOFF_BASE**restarts)

    def tick(self, store: Store, now: int) -> None:
        for task in list(store.tasks.values()):
            name = task.spec.name
            if task.phase == "Bound":
                until = self.waiting_until.get(name, 0)
                if now < until:
                    continue
                probe = self.probes.get(name, Probe())
                generation = task.generation
                if probe.up(task.restarts):
                    task.phase = "Running"
                    self.last_healthy[name] = now
                    if self.startup_gate is not None:
                        self.startup_gate.note_up(name)
                elif self.startup_gate is not None:
                    ruling = self.startup_gate.admit_failure(name)
                    if ruling == "broken":
                        task.phase = "Failed"
                    elif ruling == "restart":
                        task.restarts += 1
                        self.restarts += 1
                        self.waiting_until[name] = now + self.backoff_for(
                            task.restarts
                        )
                    else:
                        task.restarts += 1
                else:
                    task.restarts += 1
                    self.restarts += 1
                    self.waiting_until[name] = now + self.backoff_for(task.restarts)
                store.update_task(task, read_generation=generation)
            elif task.phase == "Running":
                healthy_since = self.last_healthy.get(name, now)
                if task.restarts and now - healthy_since >= FORGIVE_AFTER:
                    generation = task.generation
                    task.restarts = 0
                    store.update_task(task, read_generation=generation)
                    self.forgiven += 1
