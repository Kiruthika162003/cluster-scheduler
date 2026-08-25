"""The service catalog: every deploy has an owner, and the pager knows them.

An entry binds a deploy to a team, a channel, and an escalation chain.
The catalog answers the incident question, who do I wake, and the
governance question, what has no owner, because unowned services are
owned by whoever is on call the night they break. Escalation walks the
chain in order and says when it has run out of humans, which is the
moment the incident becomes everyone's.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import NotFound
from fleet.store import Store


@dataclass(frozen=True)
class CatalogEntry:
    deploy: str
    team: str
    channel: str
    escalation: tuple[str, ...]


@dataclass
class Catalog:
    entries: dict[str, CatalogEntry] = field(default_factory=dict)

    def register(self, entry: CatalogEntry) -> None:
        self.entries[entry.deploy] = entry

    def owner_of(self, deploy: str) -> CatalogEntry:
        if deploy not in self.entries:
            raise NotFound(f"{deploy} has no catalog entry")
        return self.entries[deploy]

    def page_target(self, deploy: str, attempt: int) -> str:
        entry = self.owner_of(deploy)
        if attempt < len(entry.escalation):
            return entry.escalation[attempt]
        return "everyone: the chain is exhausted"

    def unowned_deploys(self, store: Store) -> list[str]:
        running = {
            task.spec.label_map().get("deploy")
            for task in store.tasks.values()
            if task.is_active() and task.spec.label_map().get("deploy")
        }
        return sorted(name for name in running if name not in self.entries)

    def team_page(self, team: str) -> list[str]:
        return sorted(
            entry.deploy
            for entry in self.entries.values()
            if entry.team == team
        )
