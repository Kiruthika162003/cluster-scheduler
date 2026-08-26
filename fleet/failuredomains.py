"""Failure domains: the audit asks what one rack takes with it.

Spread rules act at placement time; this audit asks the after
question: given where everything actually landed, what fraction of
each deploy dies when rack R loses power, when zone Z loses
network. The answer is computed per domain level from node labels,
the worst domain is named with its share, and concentration is
graded against the only rule that matters: losing one domain must
not take a deploy below its quorum or its serving floor. A deploy
with all three replicas alive but stacked on one rack passes every
health check and fails this audit, which is the audit's entire
reason to exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.store import Store


@dataclass(frozen=True)
class Exposure:
    deploy: str
    level: str
    domain: str
    lost: int
    total: int

    def share(self) -> float:
        return round(self.lost / self.total, 3)

    def line(self) -> str:
        return (
            f"{self.deploy}: losing {self.level} {self.domain} kills "
            f"{self.lost} of {self.total} ({self.share():.0%})"
        )


@dataclass
class DomainAudit:
    store: Store
    levels: tuple[str, ...] = ("rack", "zone")
    floors: dict[str, int] = field(default_factory=dict)

    def _deploy_of(self, task) -> str:
        return task.spec.name.rsplit("-", 1)[0]

    def _placements(self) -> dict[str, list[str]]:
        by_deploy: dict[str, list[str]] = {}
        for task in self.store.active_tasks():
            if task.node is None:
                continue
            by_deploy.setdefault(self._deploy_of(task), []).append(task.node)
        return by_deploy

    def worst_exposures(self) -> list[Exposure]:
        exposures = []
        for deploy, nodes in sorted(self._placements().items()):
            for level in self.levels:
                per_domain: dict[str, int] = {}
                for node_name in nodes:
                    node = self.store.get_node(node_name)
                    domain = node.labels.get(level)
                    if domain is None:
                        raise Invalid(
                            f"{node_name} carries no {level} label; "
                            f"the audit cannot see its blast radius"
                        )
                    per_domain[domain] = per_domain.get(domain, 0) + 1
                worst = max(sorted(per_domain), key=lambda d: per_domain[d])
                exposures.append(
                    Exposure(
                        deploy=deploy,
                        level=level,
                        domain=worst,
                        lost=per_domain[worst],
                        total=len(nodes),
                    )
                )
        return exposures

    def verdicts(self) -> list[str]:
        failed = []
        for exposure in self.worst_exposures():
            floor = self.floors.get(exposure.deploy, 1)
            survivors = exposure.total - exposure.lost
            if survivors < floor:
                failed.append(
                    f"{exposure.line()}, leaving {survivors} against a "
                    f"floor of {floor}"
                )
        return failed

    def report(self) -> str:
        failed = self.verdicts()
        if not failed:
            return "every deploy survives its worst single domain"
        lines = [f"{len(failed)} deploy-level(s) concentrated:"]
        lines.extend(f"  {line}" for line in failed)
        return "\n".join(lines)
