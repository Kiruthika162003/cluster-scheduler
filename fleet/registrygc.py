"""Registry garbage collection: the digest you deleted is the rollback you needed.

Digests pile up in the registry; the collector reclaims what nothing
references. The whole question is what counts as a reference. Running
tasks, obviously. The eager collector stops there and deletes every
digest the fleet is not executing this minute, which includes the last
known-good build the moment its rollout completes. The careful
collector also counts revision history as references, so a rollback
target survives exactly as long as the history that would name it. The
difference is invisible until the night it is everything.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.roll.history import History
from fleet.store import Store

IMAGE_LABEL = "image"


@dataclass
class DigestStore:
    digests: dict[str, int] = field(default_factory=dict)
    deleted: list[str] = field(default_factory=list)

    def push(self, digest: str, size: int = 100) -> None:
        self.digests[digest] = size

    def holds(self, digest: str) -> bool:
        return digest in self.digests

    def stored_size(self) -> int:
        return sum(self.digests.values())


def running_references(store: Store) -> set[str]:
    return {
        task.spec.label_map()[IMAGE_LABEL]
        for task in store.tasks.values()
        if IMAGE_LABEL in task.spec.label_map()
        and task.phase not in ("Succeeded", "Failed")
    }


def history_references(histories: list[History]) -> set[str]:
    held = set()
    for history in histories:
        for entry in history.entries:
            image = dict(entry.template.labels).get(IMAGE_LABEL)
            if image is not None:
                held.add(image)
    return held


def collect(
    registry: DigestStore,
    store: Store,
    histories: list[History],
    careful: bool,
) -> list[str]:
    referenced = running_references(store)
    if careful:
        referenced |= history_references(histories)
    doomed = sorted(set(registry.digests) - referenced)
    for digest in doomed:
        del registry.digests[digest]
        registry.deleted.append(digest)
    return doomed
