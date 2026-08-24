"""Services and endpoints: traffic goes where readiness says, and only there.

A service selects tasks by label; its endpoints are the selected tasks
that are Running on ready nodes and passing their readiness probe.
Liveness and readiness fail differently on purpose: a liveness failure
restarts the task, a readiness failure only removes it from the
endpoints, because a task that is briefly unable to serve is not a
task that needs killing, and killing it turns a warmup into an outage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.store import Store


@dataclass(frozen=True)
class Service:
    name: str
    selector_key: str
    selector_value: str


@dataclass
class Readiness:
    """Scripted readiness per task: the set of ticks it reports unready."""

    unready_at: dict[str, frozenset[int]] = field(default_factory=dict)
    removals: int = 0
    returns: int = 0
    last: dict[str, bool] = field(default_factory=dict)

    def is_ready(self, task_name: str, now: int) -> bool:
        ready = now not in self.unready_at.get(task_name, frozenset())
        before = self.last.get(task_name, True)
        if before and not ready:
            self.removals += 1
        if not before and ready:
            self.returns += 1
        self.last[task_name] = ready
        return ready


def endpoints(
    store: Store, service: Service, readiness: Readiness, now: int
) -> list[str]:
    chosen = []
    for task in store.tasks.values():
        if task.spec.label_map().get(service.selector_key) != service.selector_value:
            continue
        if task.phase != "Running" or task.node is None:
            continue
        node = store.nodes.get(task.node)
        if node is None or not node.ready:
            continue
        if not readiness.is_ready(task.spec.name, now):
            continue
        chosen.append(task.spec.name)
    return sorted(chosen)
