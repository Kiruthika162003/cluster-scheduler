"""Cluster invariants: sentences that must hold after every single tick.

Each invariant is a predicate over the whole store with a sentence for
its violation. The checker runs them all and returns every broken
sentence rather than the first, because invariant violations arrive in
families and the second one is usually the cause of the first. The sim
tests run the checker after every tick, which is what makes refactoring
the controllers survivable.
"""

from __future__ import annotations

from fleet.store import Store


def bound_tasks_name_real_nodes(store: Store) -> list[str]:
    broken = []
    for task in store.tasks.values():
        if task.is_active():
            if task.node is None:
                broken.append(f"{task.spec.name} is {task.phase} with no node")
            elif task.node not in store.nodes:
                broken.append(
                    f"{task.spec.name} is on {task.node} which does not exist"
                )
    return broken


def pending_tasks_have_no_node(store: Store) -> list[str]:
    return [
        f"{task.spec.name} is Pending but still holds {task.node}"
        for task in store.tasks.values()
        if task.phase == "Pending" and task.node is not None
    ]


def no_node_is_overcommitted(store: Store) -> list[str]:
    broken = []
    active = store.active_tasks()
    for node in store.nodes.values():
        cpu = sum(t.spec.needs.cpu for t in active if t.node == node.name)
        memory = sum(t.spec.needs.memory for t in active if t.node == node.name)
        over_cpu = cpu - node.capacity.cpu
        over_memory = memory - node.capacity.memory
        if over_cpu > 0 or over_memory > 0:
            broken.append(
                f"{node.name} is overcommitted by "
                f"{max(over_cpu, 0)}m cpu {max(over_memory, 0)}Mi memory"
            )
    return broken


def finished_tasks_hold_nothing(store: Store) -> list[str]:
    return [
        f"{task.spec.name} is {task.phase} but still holds {task.node}"
        for task in store.tasks.values()
        if task.phase in ("Succeeded", "Failed", "Evicted") and task.node is not None
    ]


def generations_only_grow(store: Store) -> list[str]:
    return [
        f"{task.spec.name} has generation {task.generation}"
        for task in store.tasks.values()
        if task.generation < 1
    ]


EVERY_INVARIANT = (
    bound_tasks_name_real_nodes,
    pending_tasks_have_no_node,
    no_node_is_overcommitted,
    finished_tasks_hold_nothing,
    generations_only_grow,
)


def violations(store: Store) -> list[str]:
    broken: list[str] = []
    for invariant in EVERY_INVARIANT:
        broken.extend(invariant(store))
    return broken


def assert_clean(store: Store) -> None:
    broken = violations(store)
    if broken:
        raise AssertionError("; ".join(broken))
