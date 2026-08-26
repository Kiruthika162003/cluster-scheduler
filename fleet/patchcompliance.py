"""Patch compliance: exposure is measured in node-days, not in advisories.

An advisory list says what is dangerous; it does not say how much
of it you are running or for how long you have known. The tracker
joins the two: each node reports its image version, each advisory
names the versions it affects and the tick it was published, and
exposure per advisory is the sum over affected nodes of ticks
since publication, because five nodes unpatched for a hundred
ticks is a different fact from a hundred nodes unpatched for five.
The deadline policy grades by severity: critical advisories get a
short fuse and the report names every node past its fuse, which is
the list someone should be walking tonight. Patching a node stops
its meter; nothing else does.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid

FUSES = {"critical": 14, "high": 45, "medium": 90}


@dataclass(frozen=True)
class Advisory:
    name: str
    severity: str
    affects: tuple[str, ...]
    published: int

    def __post_init__(self) -> None:
        if self.severity not in FUSES:
            raise Invalid(f"unknown severity {self.severity}")
        if not self.affects:
            raise Invalid(f"{self.name} affects nothing; why file it")


@dataclass
class ComplianceTracker:
    versions: dict[str, str] = field(default_factory=dict)
    advisories: dict[str, Advisory] = field(default_factory=dict)

    def node_runs(self, node: str, version: str) -> None:
        self.versions[node] = version

    def publish(self, advisory: Advisory) -> None:
        if advisory.name in self.advisories:
            raise Invalid(f"{advisory.name} was already published")
        self.advisories[advisory.name] = advisory

    def exposed_nodes(self, advisory_name: str) -> list[str]:
        advisory = self.advisories.get(advisory_name)
        if advisory is None:
            raise Invalid(f"no advisory named {advisory_name}")
        return sorted(
            node
            for node, version in self.versions.items()
            if version in advisory.affects
        )

    def exposure_node_ticks(self, advisory_name: str, now: int) -> int:
        advisory = self.advisories[advisory_name]
        exposed = self.exposed_nodes(advisory_name)
        return max(0, now - advisory.published) * len(exposed)

    def past_the_fuse(self, now: int) -> list[tuple[str, str, int]]:
        rows = []
        for name in sorted(self.advisories):
            advisory = self.advisories[name]
            fuse = FUSES[advisory.severity]
            overdue = now - advisory.published - fuse
            if overdue <= 0:
                continue
            for node in self.exposed_nodes(name):
                rows.append((node, name, overdue))
        return sorted(rows, key=lambda row: (-row[2], row[0]))

    def report(self, now: int) -> str:
        if not self.advisories:
            return "no advisories on file"
        lines = []
        for name in sorted(self.advisories):
            advisory = self.advisories[name]
            exposed = self.exposed_nodes(name)
            ticks = self.exposure_node_ticks(name, now)
            lines.append(
                f"{name} ({advisory.severity}): {len(exposed)} nodes, "
                f"{ticks} node-ticks of exposure"
            )
        overdue = self.past_the_fuse(now)
        if overdue:
            lines.append(f"{len(overdue)} node(s) past the fuse:")
            for node, advisory_name, days in overdue:
                lines.append(
                    f"  {node} vs {advisory_name}: {days} past deadline"
                )
        return "\n".join(lines)
