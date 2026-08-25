"""Control plane cold start: rebuild everything from the store, prove nothing moved.

The engine's queue, the informer caches, the deployer's ownership maps
are all derived state. A control plane restart throws them away, and
the rebuild has one correctness bar: the recovered plane must make the
same decisions the uninterrupted one would have. The reconstruction
reads only the store, pending tasks re-enter the queue with their spec
priorities, and the twin test runs an interrupted and an uninterrupted
plane forward to demand identical placements, which is what nobody
notices means.
"""

from __future__ import annotations

from fleet.control.watch import Informer
from fleet.sched.placement import Engine
from fleet.store import Store


def rebuild_engine(store: Store) -> Engine:
    engine = Engine()
    for task in sorted(store.pending_tasks(), key=lambda held: held.spec.name):
        engine.queue.offer(
            task.spec.name, task.spec.priority, task.spec.namespace
        )
    return engine


def rebuild_informer(store: Store) -> Informer:
    informer = Informer()
    informer.refresh(store)
    return informer


def cold_start(store: Store) -> tuple[Engine, Informer]:
    return rebuild_engine(store), rebuild_informer(store)
