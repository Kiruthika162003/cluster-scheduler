"""Runbooks as data: the procedure is executable and the gate comes first.

A runbook is a named sequence of facade verbs with its preflight built
in: the drain runbook refuses to begin when the preflight objects, and
every step it takes is journalled so the incident review reads one
thread instead of a scatter of verbs. The drill harness runs a runbook
against a fleet and hands back a ruling, because a runbook that has
never been drilled is a wish with formatting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.api import Fleet
from fleet.objects import Node
from fleet.preflight import drain_preflight
from fleet.verify import violations


@dataclass
class RunbookResult:
    runbook: str
    steps: list[str] = field(default_factory=list)
    refused: str | None = None

    def ran(self) -> bool:
        return self.refused is None


@dataclass
class Runbooks:
    drills: int = 0

    def drain_node(self, fleet: Fleet, who: str, node_name: str) -> RunbookResult:
        result = RunbookResult(runbook=f"drain-node {node_name}")
        verdict = drain_preflight(fleet.store, fleet.guard, node_name)
        if not verdict.go():
            result.refused = verdict.line()
            fleet.journal.note(
                fleet.now, who, node_name, "runbook-refused", verdict.line()
            )
            return result
        evicted, refused = fleet.drain(who, node_name)
        result.steps.append(f"drained: {len(evicted)} moved, {len(refused)} held")
        placed, _ = fleet.step()
        result.steps.append(f"rescheduled: {placed} placed")
        return result

    def replace_node(self, fleet: Fleet, who: str, node_name: str) -> RunbookResult:
        result = RunbookResult(runbook=f"replace-node {node_name}")
        if node_name not in fleet.store.nodes:
            result.refused = f"{node_name} does not exist"
            return result
        capacity = fleet.store.get_node(node_name).capacity
        fresh = f"{node_name}-replacement"
        fleet.store.add_node(Node(name=fresh, capacity=capacity))
        fleet.engine.queue.shape_changed(fleet.now)
        result.steps.append(f"provisioned {fresh}")
        moved = fleet.retire_node(who, node_name)
        result.steps.append(f"retired {node_name}, {moved} tasks moved")
        placed, _ = fleet.step()
        result.steps.append(f"rescheduled: {placed} placed")
        return result

    def drill(self, fleet: Fleet, who: str, result: RunbookResult) -> str:
        del who
        self.drills += 1
        broken = violations(fleet.store)
        if not result.ran():
            return f"drill: {result.runbook} correctly refused"
        if broken:
            return f"drill FAILED: {result.runbook} left {broken[0]}"
        return f"drill: {result.runbook} left the fleet whole"
