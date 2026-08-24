"""Revision history: rollback is a pointer move, not a resurrection.

Every applied rollout is recorded with its template and revision number,
capped like any history worth keeping. Rolling back does not restore
some saved cluster state; it applies the previous revision as a brand
new rollout with a brand new revision number, because the cluster only
ever moves forward and the history is a menu, not a time machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import NotFound
from fleet.objects import TaskSpec
from fleet.roll.rolling import Rollout


@dataclass(frozen=True)
class Entry:
    revision: int
    template: TaskSpec
    note: str


@dataclass
class History:
    name: str
    keep: int = 10
    entries: list[Entry] = field(default_factory=list)
    next_revision: int = 1

    def record(self, template: TaskSpec, note: str = "") -> int:
        revision = self.next_revision
        self.entries.append(Entry(revision=revision, template=template, note=note))
        self.next_revision += 1
        while len(self.entries) > self.keep:
            self.entries.pop(0)
        return revision

    def current(self) -> Entry:
        if not self.entries:
            raise NotFound(f"{self.name} has no revisions")
        return self.entries[-1]

    def find(self, revision: int) -> Entry:
        for entry in self.entries:
            if entry.revision == revision:
                return entry
        raise NotFound(f"{self.name} revision {revision}")

    def rollout(self, replicas: int, **limits) -> Rollout:
        entry = self.current()
        return Rollout(
            name=self.name,
            replicas=replicas,
            template=entry.template,
            revision=entry.revision,
            **limits,
        )

    def rollback_to(self, revision: int, replicas: int, **limits) -> Rollout:
        """Re-apply an old template under a new revision number."""
        old = self.find(revision)
        fresh = self.record(old.template, note=f"rollback of r{revision}")
        return Rollout(
            name=self.name,
            replicas=replicas,
            template=old.template,
            revision=fresh,
            **limits,
        )
