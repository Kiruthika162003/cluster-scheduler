"""Filters: every reason a node says no, said in words.

A filter looks at one task and one node and either passes or returns the
sentence explaining the refusal. The scheduler keeps every sentence, so
an unschedulable task's error is a map from node name to reason instead
of a shrug. Nothing here scores; a filter that starts ranking has taken
a second job.
"""

from __future__ import annotations

from fleet.objects import Node, Task, free


def fits(task: Task, node: Node, active: list[Task]) -> str | None:
    room = free(node, active)
    needs = task.spec.needs
    if needs.cpu > room.cpu:
        return f"needs {needs.cpu}m cpu, {room.cpu}m free"
    if needs.memory > room.memory:
        return f"needs {needs.memory}Mi memory, {room.memory}Mi free"
    return None


def is_ready(task: Task, node: Node, active: list[Task]) -> str | None:
    if not node.ready:
        return "node not ready"
    return None


def selector_matches(task: Task, node: Node, active: list[Task]) -> str | None:
    for key, wanted in task.spec.selector:
        held = node.labels.get(key)
        if held != wanted:
            return f"selector {key}={wanted}, node has {held}"
    return None


def tolerates_taints(task: Task, node: Node, active: list[Task]) -> str | None:
    for taint in node.taints:
        if taint.effect == "NoSchedule" and taint.key not in task.spec.tolerates:
            return f"untolerated taint {taint.key}"
    return None


def repelled_by_peers(task: Task, node: Node, active: list[Task]) -> str | None:
    mine = task.spec.label_map()
    for other in active:
        if other.node != node.name or other.spec.name == task.spec.name:
            continue
        theirs = other.spec.label_map()
        for key in task.spec.repels:
            if key in mine and theirs.get(key) == mine[key]:
                return f"anti-affinity on {key} with {other.spec.name}"
    return None


EVERY_FILTER = (
    is_ready,
    selector_matches,
    tolerates_taints,
    repelled_by_peers,
    fits,
)
