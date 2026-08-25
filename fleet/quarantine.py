"""Node quarantine: the node that keeps killing tasks loses custody.

One task crash is the task's fault; the same node killing tasks from
different deploys inside a short window is the node's. The warden
counts distinct victims per node, quarantines at the threshold by
cordoning and tainting, and starts a probation clock. A node that
stays clean through probation is released; a node that kills again
inside probation restarts the clock doubled, up to a ceiling, which
is backoff applied to hardware trust. Every quarantine and release
is journaled with its victims, because "n7 again" is only actionable
if the ledger can prove the again.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.objects import Taint
from fleet.store import Store

VICTIM_THRESHOLD = 3
WINDOW = 20
PROBATION = 50
PROBATION_CEILING = 400
QUARANTINE_TAINT = "quarantined"


@dataclass
class NodeRecord:
    kills: list[tuple[int, str, str]] = field(default_factory=list)
    quarantined_at: int | None = None
    probation: int = PROBATION
    stints: int = 0


@dataclass
class Warden:
    records: dict[str, NodeRecord] = field(default_factory=dict)
    journal: list[str] = field(default_factory=list)

    def _record(self, node: str) -> NodeRecord:
        return self.records.setdefault(node, NodeRecord())

    def task_died(
        self, store: Store, node: str, task: str, deploy: str, now: int
    ) -> str | None:
        record = self._record(node)
        record.kills.append((now, task, deploy))
        if record.quarantined_at is not None:
            record.probation = min(PROBATION_CEILING, record.probation * 2)
            record.quarantined_at = now
            self.journal.append(
                f"[{now}] {node} killed {task} inside probation; "
                f"clock restarts at {record.probation}"
            )
            return "probation restarted"
        recent = [
            (tick, victim, owner)
            for tick, victim, owner in record.kills
            if now - tick <= WINDOW
        ]
        owners = {owner for _, _, owner in recent}
        if len(owners) < 2 or len(recent) < VICTIM_THRESHOLD:
            return None
        return self._quarantine(store, node, recent, now)

    def _quarantine(
        self, store: Store, node: str, recent: list, now: int
    ) -> str:
        record = self._record(node)
        record.quarantined_at = now
        record.stints += 1
        held = store.get_node(node)
        held.schedulable = False
        if not any(t.key == QUARANTINE_TAINT for t in held.taints):
            held.taints = (
                *held.taints,
                Taint(key=QUARANTINE_TAINT, effect="NoSchedule"),
            )
        victims = ", ".join(victim for _, victim, _ in recent)
        self.journal.append(
            f"[{now}] {node} quarantined: killed {victims} "
            f"across {len({o for _, _, o in recent})} deploys"
        )
        return "quarantined"

    def patrol(self, store: Store, now: int) -> list[str]:
        released = []
        for node, record in sorted(self.records.items()):
            if record.quarantined_at is None:
                continue
            if now - record.quarantined_at < record.probation:
                continue
            record.quarantined_at = None
            record.kills.clear()
            held = store.get_node(node)
            held.schedulable = True
            held.taints = tuple(
                taint
                for taint in held.taints
                if taint.key != QUARANTINE_TAINT
            )
            self.journal.append(
                f"[{now}] {node} released after clean probation "
                f"(stint {record.stints})"
            )
            released.append(node)
        return released

    def quarantined(self) -> list[str]:
        return sorted(
            node
            for node, record in self.records.items()
            if record.quarantined_at is not None
        )

    def report(self) -> str:
        lines = [f"{len(self.quarantined())} nodes in quarantine"]
        lines.extend(f"  {line}" for line in self.journal[-6:])
        return "\n".join(lines)
