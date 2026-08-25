"""Sidecars: the companion shares the node, the fate, and the paperwork.

A sidecar is declared against a primary and the keeper enforces the
three clauses of the contract: placement, the sidecar runs on the
primary's node or nowhere; fate, when the primary leaves its node the
sidecar leaves too; and cleanup, a finished primary takes its sidecar
with it, because an orphaned log-shipper shipping logs for a dead
service is the most loyal bug in production.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from fleet.objects import Resources, Task
from fleet.store import Store


@dataclass
class SidecarKeeper:
    pairs: dict[str, str] = field(default_factory=dict)
    created: int = 0
    removed: int = 0
    log: list[str] = field(default_factory=list)

    def attach(
        self,
        store: Store,
        primary_name: str,
        needs: Resources,
        suffix: str = "side",
    ) -> str:
        sidecar_name = f"{primary_name}-{suffix}"
        primary = store.get_task(primary_name)
        sidecar = Task(
            spec=replace(
                primary.spec,
                name=sidecar_name,
                needs=needs,
                labels=(
                    *primary.spec.labels,
                    ("sidecar-of", primary_name),
                ),
            )
        )
        store.add_task(sidecar)
        self.pairs[sidecar_name] = primary_name
        self.created += 1
        return sidecar_name

    def reconcile(self, store: Store) -> list[str]:
        actions = []
        for sidecar_name, primary_name in list(self.pairs.items()):
            sidecar = store.tasks.get(sidecar_name)
            primary = store.tasks.get(primary_name)
            if sidecar is None:
                del self.pairs[sidecar_name]
                continue
            if primary is None or primary.phase in ("Succeeded", "Failed"):
                store.remove_task(sidecar_name)
                del self.pairs[sidecar_name]
                self.removed += 1
                actions.append(f"{sidecar_name} removed with its primary")
                continue
            if primary.is_active() and sidecar.node != primary.node:
                generation = sidecar.generation
                sidecar.node = primary.node
                sidecar.phase = "Bound"
                store.update_task(sidecar, read_generation=generation)
                actions.append(
                    f"{sidecar_name} follows {primary_name} to {primary.node}"
                )
            elif not primary.is_active() and sidecar.is_active():
                generation = sidecar.generation
                sidecar.phase = "Pending"
                sidecar.node = None
                store.update_task(sidecar, read_generation=generation)
                actions.append(f"{sidecar_name} shares the fate of {primary_name}")
        self.log.extend(actions)
        return actions
