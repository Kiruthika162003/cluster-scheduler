"""The rebalancer: buy back headroom with a bounded number of moves.

Churn fragments a cluster: capacity ends up as slivers no large task can
use. The rebalancer moves tasks strictly up-hill, from emptier nodes
onto fuller ones, spending from a move budget because every move is a
disruption someone feels. The up-hill rule is not a preference, it is
the termination proof: the first draft happily moved a task between two
equally loaded nodes forever, eight wasted moves of a ten move budget,
because improvement was assumed instead of required. Strictness alone
then froze the perfectly symmetric cluster, every node equally loaded
being nobody's up-hill, so equal loads may move only toward the smaller
name: the pair orders every state and the walk must end.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.objects import Node, Task, free
from fleet.store import Store


@dataclass
class Move:
    task: str
    source: str
    target: str


@dataclass
class Rebalancer:
    budget: int
    moves: list[Move] = field(default_factory=list)

    def largest_placeable(self, store: Store) -> int:
        active = store.active_tasks()
        best = 0
        for node in store.nodes.values():
            if not node.ready:
                continue
            room = free(node, active)
            best = max(best, min(room.cpu, room.memory))
        return best

    def _emptiest_nodes(self, store: Store) -> list[Node]:
        active = store.active_tasks()

        def load(node: Node) -> int:
            return sum(
                task.spec.needs.cpu
                for task in active
                if task.node == node.name
            )

        return sorted(
            (node for node in store.nodes.values() if node.ready),
            key=lambda node: (load(node), node.name),
        )

    def _load(self, store: Store, node_name: str) -> int:
        return sum(
            task.spec.needs.cpu
            for task in store.active_tasks()
            if task.node == node_name
        )

    def _fits_uphill(self, store: Store, task: Task, source: str) -> str | None:
        active = store.active_tasks()
        source_load = self._load(store, source)
        candidates = sorted(
            (node for node in store.nodes.values() if node.ready),
            key=lambda node: (-self._load(store, node.name), node.name),
        )
        for node in candidates:
            if node.name == source:
                continue
            load = self._load(store, node.name)
            uphill = load > source_load or (load == source_load and node.name < source)
            if not uphill:
                continue
            if task.spec.needs.fits_in(free(node, active)):
                return node.name
        return None

    def rebalance(self, store: Store) -> int:
        """Consolidate until the budget runs out or no move helps."""
        spent = 0
        while spent < self.budget:
            moved = False
            for node in self._emptiest_nodes(store):
                tenants = sorted(
                    (
                        task
                        for task in store.active_tasks()
                        if task.node == node.name
                    ),
                    key=lambda task: task.spec.name,
                )
                if not tenants:
                    continue
                for task in tenants:
                    target = self._fits_uphill(store, task, source=node.name)
                    if target is None:
                        continue
                    generation = task.generation
                    task.node = target
                    store.update_task(task, read_generation=generation)
                    self.moves.append(
                        Move(task=task.spec.name, source=node.name, target=target)
                    )
                    spent += 1
                    moved = True
                    break
                if moved:
                    break
            if not moved:
                break
        return spent
