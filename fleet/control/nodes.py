"""The node lifecycle: silence, suspicion, eviction, return.

Nodes heartbeat; the monitor marks a silent node NotReady after a grace
period and evicts its tasks after a longer one. The two timers are
different on purpose: flapping networks should cost scheduling
eligibility quickly and running workloads slowly. A node that comes
back before the eviction timer keeps every task it had.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.store import Store

NOT_READY_AFTER = 3
EVICT_AFTER = 10


@dataclass
class Monitor:
    marked_not_ready: int = 0
    marked_ready: int = 0
    evicted: int = 0
    evictions_by_node: dict[str, int] = field(default_factory=dict)

    def beat(self, store: Store, node_name: str, now: int) -> None:
        node = store.get_node(node_name)
        node.last_heartbeat = now
        if not node.ready:
            node.ready = True
            self.marked_ready += 1

    def sweep(self, store: Store, now: int) -> tuple[int, int]:
        """Returns (newly not ready, tasks evicted) this sweep."""
        turned = evicted = 0
        for node in store.nodes.values():
            silent_for = now - node.last_heartbeat
            if node.ready and silent_for > NOT_READY_AFTER:
                node.ready = False
                self.marked_not_ready += 1
                turned += 1
            if not node.ready and silent_for > EVICT_AFTER:
                for task in store.tasks.values():
                    if task.node == node.name and task.is_active():
                        generation = task.generation
                        task.phase = "Pending"
                        task.node = None
                        task.restarts += 1
                        store.update_task(task, read_generation=generation)
                        self.evicted += 1
                        evicted += 1
                        self.evictions_by_node[node.name] = (
                            self.evictions_by_node.get(node.name, 0) + 1
                        )
        return turned, evicted
