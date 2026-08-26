"""Inventory reconciliation: the fleet you bill is not the fleet you see.

Procurement's ledger says 40 nodes; the cluster sees 37. The other
three are the interesting part: a node in the ledger but not the
cluster is dark inventory, paid for and doing nothing; a node in
the cluster but not the ledger is a ghost, doing work nobody
approved and nobody will patch; a node in both but with different
hardware is a swap someone made in the aisle and never wrote down.
The reconciler produces all three lists with the evidence attached,
and the drift score is their combined share of the ledger, because
one number is what makes the monthly review notice the trend
instead of the anecdotes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.store import Store


@dataclass(frozen=True)
class LedgerEntry:
    name: str
    cpu: int
    memory: int


@dataclass
class Reconciliation:
    dark: list[str] = field(default_factory=list)
    ghosts: list[str] = field(default_factory=list)
    swapped: list[str] = field(default_factory=list)
    matched: int = 0

    def drift_score(self, ledger_size: int) -> float:
        if ledger_size == 0:
            raise Invalid("an empty ledger cannot drift")
        troubled = len(self.dark) + len(self.ghosts) + len(self.swapped)
        return round(troubled / ledger_size, 3)

    def clean(self) -> bool:
        return not (self.dark or self.ghosts or self.swapped)


def reconcile(ledger: list[LedgerEntry], store: Store) -> Reconciliation:
    if len({entry.name for entry in ledger}) != len(ledger):
        raise Invalid("the ledger lists a node twice")
    result = Reconciliation()
    by_name = {entry.name: entry for entry in ledger}
    for name in sorted(by_name):
        if name not in store.nodes:
            result.dark.append(name)
    for name in sorted(store.nodes):
        node = store.nodes[name]
        entry = by_name.get(name)
        if entry is None:
            result.ghosts.append(name)
            continue
        if (
            node.capacity.cpu != entry.cpu
            or node.capacity.memory != entry.memory
        ):
            result.swapped.append(
                f"{name}: ledger says {entry.cpu}m/{entry.memory}, "
                f"metal says {node.capacity.cpu}m/{node.capacity.memory}"
            )
            continue
        result.matched += 1
    return result


def report(ledger: list[LedgerEntry], store: Store) -> str:
    result = reconcile(ledger, store)
    if result.clean():
        return f"clean: all {result.matched} nodes match the ledger"
    lines = [
        f"drift {result.drift_score(len(ledger)):.1%}: "
        f"{result.matched} matched"
    ]
    for name in result.dark:
        lines.append(f"  dark: {name} is billed but absent")
    for name in result.ghosts:
        lines.append(f"  ghost: {name} works here but nobody approved it")
    for line in result.swapped:
        lines.append(f"  swapped: {line}")
    return "\n".join(lines)
