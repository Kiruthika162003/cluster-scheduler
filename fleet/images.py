"""Images by digest: the tag is a rumour, the digest is a fact.

A tag like latest names whatever the registry holds at the moment of
the pull, so two replicas created an hour apart can run different
software while claiming the same version. The resolver pins a tag to
its digest at rollout time and stamps every task with the digest, so a
rollout is one build by construction. The registry model here moves
tags the way real registries do: silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import NotFound


@dataclass
class Registry:
    tags: dict[str, str] = field(default_factory=dict)
    pushes: int = 0

    def push(self, tag: str, digest: str) -> None:
        self.tags[tag] = digest
        self.pushes += 1

    def resolve(self, tag: str) -> str:
        if tag not in self.tags:
            raise NotFound(f"tag {tag}")
        return self.tags[tag]


@dataclass
class PullLog:
    """What each task actually ran, by name."""

    ran: dict[str, str] = field(default_factory=dict)

    def pull_by_tag(self, registry: Registry, task_name: str, tag: str) -> str:
        digest = registry.resolve(tag)
        self.ran[task_name] = digest
        return digest

    def pull_by_digest(self, task_name: str, digest: str) -> str:
        self.ran[task_name] = digest
        return digest

    def builds_running(self) -> set[str]:
        return set(self.ran.values())


def rollout_by_tag(
    registry: Registry, log: PullLog, tag: str, replicas: int, move_at: int, new_digest: str
) -> set[str]:
    """Create replicas one at a time; the tag moves mid-rollout."""
    for number in range(replicas):
        if number == move_at:
            registry.push(tag, new_digest)
        log.pull_by_tag(registry, f"web-{number}", tag)
    return log.builds_running()


def rollout_by_digest(
    registry: Registry, log: PullLog, tag: str, replicas: int, move_at: int, new_digest: str
) -> set[str]:
    """Resolve once, stamp the digest, and let the tag do what it likes."""
    pinned = registry.resolve(tag)
    for number in range(replicas):
        if number == move_at:
            registry.push(tag, new_digest)
        log.pull_by_digest(f"web-{number}", pinned)
    return log.builds_running()
