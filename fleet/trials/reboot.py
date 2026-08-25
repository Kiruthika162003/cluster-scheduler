"""The control plane reboots mid-story and nobody notices, by construction.

Twelve tasks of mixed priority flow toward three nodes; after the
fourth pass the control plane is discarded, a new engine and informer
are rebuilt from the store alone, and both planes run the remaining
passes. The twin that never rebooted and the twin that did end with
identical placements task for task and an informer cache that matches
the store exactly. Derived state that can be rebuilt bit-for-identical
is the license to crash; the trial is the license renewal.
"""

from __future__ import annotations

from fleet.coldstart import cold_start
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.placement import Engine
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _seeded() -> tuple[Store, Engine]:
    store = Store()
    for number in range(3):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    engine = Engine()
    for number in range(12):
        engine.submit(
            store,
            Task(
                spec=TaskSpec(
                    name=f"t{number:02d}",
                    needs=Resources(cpu=400, memory=400),
                    priority=(number % 3) * 100,
                )
            ),
        )
    return store, engine


def _placements(store: Store) -> dict[str, str | None]:
    return {task.spec.name: task.node for task in store.tasks.values()}


def run() -> Verdict:
    steady_store, steady_engine = _seeded()
    for now in range(10):
        steady_engine.one_pass(steady_store, now)

    reboot_store, doomed_engine = _seeded()
    for now in range(4):
        doomed_engine.one_pass(reboot_store, now)
    reborn_engine, informer = cold_start(reboot_store)
    for now in range(4, 10):
        reborn_engine.one_pass(reboot_store, now)

    same = _placements(steady_store) == _placements(reboot_store)
    informer.refresh(reboot_store)

    numbers = {
        "placements_identical": same,
        "placed_steady": steady_engine.placed,
        "placed_across_reboot": doomed_engine.placed + reborn_engine.placed,
        "informer_synced": informer.agrees_with(reboot_store),
    }
    holds = (
        same
        and steady_engine.placed == doomed_engine.placed + reborn_engine.placed
        and informer.agrees_with(reboot_store)
    )
    return Verdict(
        trial="reboot",
        sentence=(
            "the plane rebuilt from the store alone finishes the story "
            "with placements identical to the twin that never crashed, "
            "and the placed counters split across the reboot sum to the "
            "steady twin's exactly"
        ),
        numbers=numbers,
        holds=holds,
    )
