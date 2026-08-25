"""Snapshots: the cluster as plain data, and the restore that must not drift.

A snapshot flattens the store to dictionaries, nothing cleverer than
strings and numbers, because a backup format with behaviour is a
second implementation waiting to disagree. Restore rebuilds a store
that must be indistinguishable going forward: same objects, same
generations, and the event log restarts empty by design, the one
declared difference, since replaying history into watchers that
already acted on it once is how restores double-fire side effects.
"""

from __future__ import annotations

from fleet.objects import Node, Resources, Taint, Task, TaskSpec
from fleet.store import Store


def dump(store: Store) -> dict:
    return {
        "tasks": [
            {
                "name": task.spec.name,
                "cpu": task.spec.needs.cpu,
                "memory": task.spec.needs.memory,
                "namespace": task.spec.namespace,
                "labels": list(task.spec.labels),
                "selector": list(task.spec.selector),
                "tolerates": list(task.spec.tolerates),
                "repels": list(task.spec.repels),
                "priority": task.spec.priority,
                "phase": task.phase,
                "node": task.node,
                "generation": task.generation,
                "restarts": task.restarts,
            }
            for task in store.tasks.values()
        ],
        "nodes": [
            {
                "name": node.name,
                "cpu": node.capacity.cpu,
                "memory": node.capacity.memory,
                "labels": dict(node.labels),
                "taints": [
                    {"key": taint.key, "effect": taint.effect}
                    for taint in node.taints
                ],
                "ready": node.ready,
                "schedulable": node.schedulable,
                "last_heartbeat": node.last_heartbeat,
            }
            for node in store.nodes.values()
        ],
    }


def restore(data: dict) -> Store:
    store = Store()
    for entry in data["nodes"]:
        node = Node(
            name=entry["name"],
            capacity=Resources(cpu=entry["cpu"], memory=entry["memory"]),
            labels=dict(entry["labels"]),
            taints=tuple(
                Taint(key=taint["key"], effect=taint["effect"])
                for taint in entry["taints"]
            ),
        )
        node.ready = entry["ready"]
        node.schedulable = entry["schedulable"]
        node.last_heartbeat = entry["last_heartbeat"]
        store.nodes[node.name] = node
    for entry in data["tasks"]:
        spec = TaskSpec(
            name=entry["name"],
            needs=Resources(cpu=entry["cpu"], memory=entry["memory"]),
            namespace=entry["namespace"],
            labels=tuple(tuple(pair) for pair in entry["labels"]),
            selector=tuple(tuple(pair) for pair in entry["selector"]),
            tolerates=tuple(entry["tolerates"]),
            repels=tuple(entry["repels"]),
            priority=entry["priority"],
        )
        task = Task(spec=spec)
        task.phase = entry["phase"]
        task.node = entry["node"]
        task.generation = entry["generation"]
        task.restarts = entry["restarts"]
        store.tasks[task.spec.name] = task
    return store
