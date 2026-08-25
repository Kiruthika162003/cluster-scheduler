"""Version skew: the door checks the gap, not the age.

A fleet upgrades brain-first: the control plane moves, then the nodes
follow. The skew policy bounds how far behind a node may lag, two minor
versions here, and the check runs at the door: a joining node too far
behind is refused with the arithmetic, and a control plane upgrade that
would orphan running nodes past the window is itself refused, because
the rule binds both directions or it binds nobody. Version parsing is
deliberately dull: major.minor, integers, no cleverness.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid

WINDOW = 2


def parse(version: str) -> tuple[int, int]:
    parts = version.split(".")
    if len(parts) != 2:
        raise Invalid(f"version {version} is not major.minor")
    try:
        return int(parts[0]), int(parts[1])
    except ValueError as wrong:
        raise Invalid(f"version {version} is not numeric") from wrong


def minor_gap(control: str, node: str) -> int:
    control_major, control_minor = parse(control)
    node_major, node_minor = parse(node)
    if control_major != node_major:
        return 10**6
    return control_minor - node_minor


@dataclass
class SkewGate:
    control_plane: str
    node_versions: dict[str, str] = field(default_factory=dict)
    refusals: list[str] = field(default_factory=list)

    def admit_node(self, name: str, version: str) -> None:
        gap = minor_gap(self.control_plane, version)
        if gap < 0:
            refusal = (
                f"{name} at {version} is ahead of the control plane "
                f"{self.control_plane}"
            )
            self.refusals.append(refusal)
            raise Invalid(refusal)
        if gap > WINDOW:
            refusal = (
                f"{name} at {version} lags {gap} minors behind "
                f"{self.control_plane}, window is {WINDOW}"
            )
            self.refusals.append(refusal)
            raise Invalid(refusal)
        self.node_versions[name] = version

    def upgrade_control_plane(self, version: str) -> list[str]:
        """Refuses when the move would orphan nodes; names them all."""
        orphaned = sorted(
            f"{name} at {held}"
            for name, held in self.node_versions.items()
            if minor_gap(version, held) > WINDOW
        )
        if orphaned:
            refusal = f"upgrade to {version} would orphan {', '.join(orphaned)}"
            self.refusals.append(refusal)
            raise Invalid(refusal)
        self.control_plane = version
        return sorted(self.node_versions)

    def laggards(self) -> list[str]:
        return sorted(
            name
            for name, held in self.node_versions.items()
            if minor_gap(self.control_plane, held) == WINDOW
        )
