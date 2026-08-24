"""Node pools: dedicated hardware fenced by taints, opened by tolerations.

A pool stamps its nodes with labels and a taint. The taint keeps the
general population out of the expensive machines; the toleration lets
the special workload in; and the selector makes the special workload
insist on its hardware rather than merely tolerating it, because a gpu
task that lands on a cpu node is not saved money, it is a silent
failure. The pool also answers capacity questions pool by pool, since
a full gpu pool with an empty general pool is not a full cluster.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from fleet.objects import Node, Resources, Taint, TaskSpec, free
from fleet.store import Store


@dataclass(frozen=True)
class PoolSpec:
    name: str
    count: int
    shape: Resources
    dedicated: bool = False

    def taint_key(self) -> str:
        return f"pool-{self.name}"


@dataclass
class Pools:
    specs: dict[str, PoolSpec] = field(default_factory=dict)

    def provision(self, store: Store, spec: PoolSpec) -> list[str]:
        self.specs[spec.name] = spec
        made = []
        for number in range(spec.count):
            name = f"{spec.name}-{number}"
            taints = (
                (Taint(key=spec.taint_key(), effect="NoSchedule"),)
                if spec.dedicated
                else ()
            )
            store.add_node(
                Node(
                    name=name,
                    capacity=spec.shape,
                    labels={"pool": spec.name},
                    taints=taints,
                )
            )
            made.append(name)
        return made

    def resident_spec(self, spec: PoolSpec, base: TaskSpec) -> TaskSpec:
        """The base spec re-cut to insist on this pool and tolerate its fence."""
        selector = (*base.selector, ("pool", spec.name))
        tolerates = (*base.tolerates, spec.taint_key())
        return replace(base, selector=selector, tolerates=tolerates)

    def headroom(self, store: Store, pool_name: str) -> Resources:
        total = Resources.none()
        active = store.active_tasks()
        for node in store.nodes.values():
            if node.labels.get("pool") == pool_name and node.ready:
                total = total.plus(free(node, active))
        return total
