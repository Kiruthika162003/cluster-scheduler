"""Topology spread: the skew cap keeps a zone from owning the service.

Nodes carry a zone label; a spread rule says the count of matching tasks
in the fullest and emptiest zones may differ by at most the skew. The
filter is built from the rule plus the node-to-zone map, because skew is
a property of the whole placement and a filter only sees one node: the
map is how the whole cluster fits through the keyhole.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleet.objects import Node, Task


@dataclass(frozen=True)
class SpreadRule:
    label_key: str
    label_value: str
    max_skew: int = 1


def zone_map(nodes: list[Node]) -> dict[str, str]:
    return {
        node.name: node.labels["zone"] for node in nodes if "zone" in node.labels
    }


def tallies(rule: SpreadRule, zones: dict[str, str], active: list[Task]) -> dict[str, int]:
    counts = dict.fromkeys(sorted(set(zones.values())), 0)
    for task in active:
        if task.spec.label_map().get(rule.label_key) != rule.label_value:
            continue
        zone = zones.get(task.node or "")
        if zone is not None:
            counts[zone] += 1
    return counts


def spread_filter(rule: SpreadRule, zones: dict[str, str]):
    """A filter closed over the rule and the zone map, shaped like the rest."""

    def check(task: Task, node: Node, active: list[Task]) -> str | None:
        if task.spec.label_map().get(rule.label_key) != rule.label_value:
            return None
        zone = zones.get(node.name)
        if zone is None:
            return "node has no zone"
        counts = tallies(rule, zones, active)
        counts[zone] += 1
        skew = max(counts.values()) - min(counts.values())
        if skew > rule.max_skew:
            return f"zone {zone} would skew {skew} > {rule.max_skew}"
        return None

    return check


def skew_now(rule: SpreadRule, zones: dict[str, str], active: list[Task]) -> int:
    counts = tallies(rule, zones, active)
    if not counts:
        return 0
    return max(counts.values()) - min(counts.values())
