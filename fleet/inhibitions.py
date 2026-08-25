"""Alert inhibition: when the node is down, its tasks are not separate news.

An inhibition rule says: while this source alert stands, suppress
these consequence alerts. The node-down alert inhibits task-down for
every task on that node; the zone-down alert inhibits node-down for
the zone's nodes. The count of suppressed consequences is reported on
the source page, because fifteen suppressed alerts is diagnostic
information, not noise, and the on-call reading node n2 down, 15
consequences held knows the blast radius before opening a dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rule:
    source_kind: str
    consequence_kind: str

    def applies(self, source: dict, consequence: dict) -> bool:
        if consequence.get("kind") != self.consequence_kind:
            return False
        scope = source.get("scope")
        return scope is None or consequence.get("within") == scope


@dataclass
class Inhibitor:
    rules: list[Rule] = field(default_factory=list)
    standing_sources: list[dict] = field(default_factory=list)
    suppressed: dict[str, int] = field(default_factory=dict)
    delivered: list[str] = field(default_factory=list)

    def raise_source(self, kind: str, name: str, scope: str) -> str:
        alert = {"kind": kind, "name": name, "scope": scope}
        self.standing_sources.append(alert)
        line = f"{kind} {name}"
        self.delivered.append(line)
        return line

    def clear_source(self, kind: str, name: str) -> int:
        held = [
            source
            for source in self.standing_sources
            if source["kind"] == kind and source["name"] == name
        ]
        for source in held:
            self.standing_sources.remove(source)
        return self.suppressed.pop(f"{kind} {name}", 0)

    def offer(self, kind: str, name: str, within: str) -> str | None:
        consequence = {"kind": kind, "name": name, "within": within}
        for source in self.standing_sources:
            for rule in self.rules:
                if rule.source_kind == source["kind"] and rule.applies(
                    source, consequence
                ):
                    key = f"{source['kind']} {source['name']}"
                    self.suppressed[key] = self.suppressed.get(key, 0) + 1
                    return None
        line = f"{kind} {name}"
        self.delivered.append(line)
        return line

    def source_summary(self, kind: str, name: str) -> str:
        held = self.suppressed.get(f"{kind} {name}", 0)
        return f"{kind} {name}, {held} consequences held"
