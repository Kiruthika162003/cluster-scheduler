"""The object model: specs say wanted, statuses say seen, nothing hides.

Every object is a spec the user wrote plus a status the controllers keep
current. The two halves never mix: a controller may not edit a spec, a
user edit bumps the generation, and a status always names the generation
it observed, so staleness is visible instead of silent.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from fleet.errors import Invalid


@dataclass(frozen=True)
class Resources:
    cpu: int
    memory: int

    def __post_init__(self) -> None:
        if self.cpu < 0 or self.memory < 0:
            raise Invalid(f"negative resources: cpu={self.cpu} memory={self.memory}")

    def plus(self, other: Resources) -> Resources:
        return Resources(cpu=self.cpu + other.cpu, memory=self.memory + other.memory)

    def minus(self, other: Resources) -> Resources:
        return Resources(cpu=self.cpu - other.cpu, memory=self.memory - other.memory)

    def fits_in(self, other: Resources) -> bool:
        return self.cpu <= other.cpu and self.memory <= other.memory

    @classmethod
    def none(cls) -> Resources:
        return cls(cpu=0, memory=0)


@dataclass(frozen=True)
class Taint:
    key: str
    effect: str

    def __post_init__(self) -> None:
        if self.effect not in ("NoSchedule", "PreferNoSchedule"):
            raise Invalid(f"unknown taint effect {self.effect}")


@dataclass(frozen=True)
class TaskSpec:
    name: str
    needs: Resources
    namespace: str = "default"
    labels: tuple[tuple[str, str], ...] = ()
    selector: tuple[tuple[str, str], ...] = ()
    tolerates: tuple[str, ...] = ()
    repels: tuple[str, ...] = ()
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.name:
            raise Invalid("a task needs a name")

    def label_map(self) -> dict[str, str]:
        return dict(self.labels)


PHASES = ("Pending", "Bound", "Running", "Succeeded", "Failed", "Evicted")


@dataclass
class Task:
    spec: TaskSpec
    phase: str = "Pending"
    node: str | None = None
    generation: int = 1
    observed: int = 0
    restarts: int = 0

    def bound_to(self, node: str) -> None:
        self.phase = "Bound"
        self.node = node

    def is_active(self) -> bool:
        return self.phase in ("Bound", "Running")


@dataclass
class Node:
    name: str
    capacity: Resources
    labels: dict[str, str] = field(default_factory=dict)
    taints: tuple[Taint, ...] = ()
    ready: bool = True
    last_heartbeat: int = 0

    def __post_init__(self) -> None:
        if not self.name:
            raise Invalid("a node needs a name")


def allocated(node: Node, tasks: list[Task]) -> Resources:
    total = Resources.none()
    for task in tasks:
        if task.node == node.name and task.is_active():
            total = total.plus(task.spec.needs)
    return total


def free(node: Node, tasks: list[Task]) -> Resources:
    return node.capacity.minus(allocated(node, tasks))


def relabelled(spec: TaskSpec, **changes) -> TaskSpec:
    return replace(spec, **changes)
