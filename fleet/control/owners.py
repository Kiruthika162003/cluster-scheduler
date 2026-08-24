"""Owner references: deletion cascades, orphans are chosen, never accidental.

A task may name its owner. Deleting an owner with the cascading policy
removes every descendant, depth first; deleting with the orphan policy
strips the reference and leaves the children to live as their own,
which is what an operator wants when replacing a controller without
replacing its workload. Cycles are refused at link time, because a
cascade that can chase its own tail deletes the world.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid, NotFound
from fleet.store import Store


@dataclass
class Owners:
    owner_of: dict[str, str] = field(default_factory=dict)
    cascaded: int = 0
    orphaned: int = 0

    def link(self, child: str, owner: str) -> None:
        if child == owner:
            raise Invalid(f"{child} cannot own itself")
        seen = {child}
        walk = owner
        while walk in self.owner_of:
            if walk in seen:
                raise Invalid(f"cycle through {walk}")
            seen.add(walk)
            walk = self.owner_of[walk]
        if walk in seen:
            raise Invalid(f"cycle through {walk}")
        self.owner_of[child] = owner

    def children_of(self, owner: str) -> list[str]:
        return sorted(
            child for child, held in self.owner_of.items() if held == owner
        )

    def delete_cascading(self, store: Store, name: str) -> list[str]:
        """Depth-first removal of the whole subtree; the names, leaves first."""
        removed = []
        for child in self.children_of(name):
            removed.extend(self.delete_cascading(store, child))
        if name in store.tasks:
            store.remove_task(name)
        self.owner_of.pop(name, None)
        removed.append(name)
        self.cascaded += 1
        return removed

    def delete_orphaning(self, store: Store, name: str) -> list[str]:
        """Remove the owner alone; children keep living, unreferenced."""
        freed = self.children_of(name)
        for child in freed:
            del self.owner_of[child]
            self.orphaned += 1
        if name not in store.tasks:
            raise NotFound(f"task {name}")
        store.remove_task(name)
        self.owner_of.pop(name, None)
        return freed
