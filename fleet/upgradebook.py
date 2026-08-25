"""The fleet upgrade book: gate, walk, verify, and refuse to skip steps.

A fleet upgrade is four smaller promises kept in order: the skew gate
says the versions may move, the preflight says today is survivable,
the pool refresh replaces the iron one node at a time, and conformance
afterwards says the fleet still keeps its promises. The book runs them
as one procedure with a ledger, and the ledger is the deliverable: an
upgrade whose record shows which step said no is an upgrade that can
be argued with, resumed, or abandoned on evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.api import Fleet
from fleet.conformance import Conformance
from fleet.poolrefresh import PoolRefresh, RefreshLedger
from fleet.preflight import upgrade_preflight
from fleet.skewpolicy import SkewGate


@dataclass
class UpgradeRecord:
    target: str
    steps: list[str] = field(default_factory=list)
    stopped_at: str | None = None

    def succeeded(self) -> bool:
        return self.stopped_at is None


@dataclass
class UpgradeBook:
    refresh: PoolRefresh = field(default_factory=PoolRefresh)

    def run(
        self,
        fleet: Fleet,
        gate: SkewGate,
        who: str,
        target: str,
        node_versions_after: str,
    ) -> UpgradeRecord:
        record = UpgradeRecord(target=target)

        verdict = upgrade_preflight(fleet.store, gate, target)
        if not verdict.go():
            record.stopped_at = "preflight"
            record.steps.append(verdict.line())
            return record
        record.steps.append(verdict.line())

        gate.upgrade_control_plane(target)
        record.steps.append(f"control plane at {target}")

        ledger = RefreshLedger(pool=sorted(fleet.store.nodes))
        steps = self.refresh.run(fleet, who, ledger)
        if not ledger.done():
            record.stopped_at = "refresh"
            record.steps.append(f"refresh stalled after {steps} steps")
            return record
        for name in list(gate.node_versions):
            del gate.node_versions[name]
        for name in fleet.store.nodes:
            gate.admit_node(name, node_versions_after)
        record.steps.append(f"{len(ledger.replaced)} nodes refreshed")

        suite = Conformance()
        suite.run()
        failing = suite.failing()
        if failing:
            record.stopped_at = "conformance"
            record.steps.append(
                f"conformance broke: {failing[0].name}"
            )
            return record
        record.steps.append(
            f"all {len(suite.results)} promises hold at {target}"
        )
        return record
