"""Burn-in: a joining node proves itself on canary work before it gets real work.

New iron fails in the first week or lasts for years, so the fleet
taints joiners with a burn-in fence and runs disposable canary tasks on
them for a probation window. A node that fails any canary is rejected
before production ever touched it; a node that serves its window clean
has the fence lifted. The whole point is which workloads absorb the
infant mortality: with burn-in it is tasks built to die, without it,
whatever the scheduler sent first.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.objects import Node, Resources, Taint, Task, TaskSpec
from fleet.store import Store

FENCE = "burnin"
PROBATION = 10


@dataclass
class BurnIn:
    probation: int = PROBATION
    joined_at: dict[str, int] = field(default_factory=dict)
    failures: dict[str, int] = field(default_factory=dict)
    graduated: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)

    def join(self, store: Store, name: str, cpu: int, now: int) -> Node:
        node = Node(
            name=name,
            capacity=Resources(cpu=cpu, memory=cpu),
            taints=(Taint(key=FENCE, effect="NoSchedule"),),
        )
        store.add_node(node)
        self.joined_at[name] = now
        return node

    def canary_task(self, node_name: str, ordinal: int) -> Task:
        return Task(
            spec=TaskSpec(
                name=f"canary-{node_name}-{ordinal}",
                needs=Resources(cpu=100, memory=100),
                tolerates=(FENCE,),
                labels=(("burnin-canary", node_name),),
            )
        )

    def note_canary_failure(self, node_name: str) -> None:
        self.failures[node_name] = self.failures.get(node_name, 0) + 1

    def sweep(self, store: Store, now: int) -> list[str]:
        """Graduate the clean, reject the failed; returns the sentences."""
        told = []
        for name, since in list(self.joined_at.items()):
            node = store.nodes.get(name)
            if node is None:
                del self.joined_at[name]
                continue
            if self.failures.get(name, 0) > 0:
                for task in list(store.tasks.values()):
                    if task.spec.label_map().get("burnin-canary") == name:
                        store.remove_task(task.spec.name)
                store.remove_node(name)
                self.rejected.append(name)
                del self.joined_at[name]
                told.append(f"{name} rejected in burn-in, production untouched")
                continue
            if now - since >= self.probation:
                node.taints = ()
                self.graduated.append(name)
                del self.joined_at[name]
                told.append(f"{name} graduated after {self.probation} clean ticks")
        return told
