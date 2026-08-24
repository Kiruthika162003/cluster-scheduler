"""The cluster on one screen: nodes, loads, phases, and the trials' word."""

from __future__ import annotations

import io

from fleet.objects import allocated
from fleet.store import Store


def node_table(store: Store) -> str:
    out = io.StringIO()
    out.write("node        ready  cpu_used  mem_used  tasks\n")
    active = store.active_tasks()
    for name in sorted(store.nodes):
        node = store.nodes[name]
        used = allocated(node, active)
        count = sum(1 for task in active if task.node == name)
        out.write(
            f"{name:<11} {node.ready!s:<6} "
            f"{used.cpu}/{node.capacity.cpu:<7} "
            f"{used.memory}/{node.capacity.memory:<7} {count}\n"
        )
    return out.getvalue()


def phase_table(store: Store) -> str:
    counts: dict[str, int] = {}
    for task in store.tasks.values():
        counts[task.phase] = counts.get(task.phase, 0) + 1
    out = io.StringIO()
    out.write("phase      count\n")
    for phase in sorted(counts):
        out.write(f"{phase:<10} {counts[phase]}\n")
    return out.getvalue()


def cluster_report(store: Store) -> str:
    total_cpu = sum(node.capacity.cpu for node in store.nodes.values())
    active = store.active_tasks()
    used_cpu = sum(task.spec.needs.cpu for task in active)
    header = (
        f"nodes {len(store.nodes)}, tasks {len(store.tasks)}, "
        f"cpu {used_cpu}/{total_cpu}\n\n"
    )
    return header + node_table(store) + "\n" + phase_table(store)
