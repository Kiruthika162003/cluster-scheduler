"""GitOps: the repo is the truth and the syncer is just a patient reader.

Desired state lives as a history of manifest versions; the cluster
follows the latest by reconciling toward it on every sync. The two
rules that make the pattern trustworthy: the syncer never writes the
repo, so causality flows one way, and a manual cluster change survives
only until the next sync unless someone commits it, which converts
every 2am hand-edit into either a proper change or an automatic
rollback by morning. The sync record says which commit the cluster
matches, which is the only version number that matters in an incident.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.control.deploy import Deployer
from fleet.errors import Invalid
from fleet.manifest import Manifest
from fleet.store import Store


@dataclass(frozen=True)
class Commit:
    revision: int
    manifest: Manifest
    message: str


@dataclass
class Repo:
    commits: list[Commit] = field(default_factory=list)

    def commit(self, manifest: Manifest, message: str) -> Commit:
        made = Commit(
            revision=len(self.commits) + 1, manifest=manifest, message=message
        )
        self.commits.append(made)
        return made

    def head(self) -> Commit:
        if not self.commits:
            raise Invalid("the repo has no commits")
        return self.commits[-1]


@dataclass
class Syncer:
    deployer: Deployer = field(default_factory=Deployer)
    synced_revision: int = 0
    corrections: int = 0
    log: list[str] = field(default_factory=list)

    def sync(self, store: Store, repo: Repo) -> str:
        head = repo.head()
        touched = 0
        for spec in head.manifest.deploys:
            created, deleted = self.deployer.reconcile(store, spec)
            touched += created + deleted
        if touched and self.synced_revision == head.revision:
            self.corrections += touched
            line = (
                f"r{head.revision} re-imposed, corrected {touched} drifted"
            )
        elif self.synced_revision != head.revision:
            line = f"advanced to r{head.revision}: {head.message}"
        else:
            line = f"r{head.revision} steady"
        self.synced_revision = head.revision
        self.log.append(line)
        return line
