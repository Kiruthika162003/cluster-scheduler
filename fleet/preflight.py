"""Preflight: the go or no-go a dangerous operation must earn first.

Draining a node or upgrading the plane is safe or it is not, and the
answer is scattered across modules that each know one piece: does the
workload survive N+1, do the budgets leave room to evict, is the
version skew inside the window, is anything already broken. Preflight
gathers the pieces into one verdict with every objection listed,
because the operator about to type the dangerous command deserves all
the bad news at once, not one no per attempt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.capacityplan import survives_n_plus_one
from fleet.control.budget import Guard
from fleet.errors import Invalid
from fleet.objects import Resources, free
from fleet.skewpolicy import SkewGate
from fleet.store import Store
from fleet.verify import violations


@dataclass
class Verdict:
    operation: str
    objections: list[str] = field(default_factory=list)

    def go(self) -> bool:
        return not self.objections

    def line(self) -> str:
        if self.go():
            return f"{self.operation}: go"
        listed = "; ".join(self.objections)
        return f"{self.operation}: no-go ({listed})"


def drain_preflight(store: Store, guard: Guard, node_name: str) -> Verdict:
    verdict = Verdict(operation=f"drain {node_name}")
    if node_name not in store.nodes:
        verdict.objections.append(f"{node_name} does not exist")
        return verdict
    broken = violations(store)
    if broken:
        verdict.objections.append(
            f"cluster already inconsistent: {broken[0]}"
        )
    tenants = [
        task for task in store.active_tasks() if task.node == node_name
    ]
    for task in tenants:
        may, why = guard.may_evict(store, task.spec.name)
        if not may:
            verdict.objections.append(f"{task.spec.name}: {why}")
    needed = Resources.none()
    for task in tenants:
        needed = needed.plus(task.spec.needs)
    room = Resources.none()
    active = store.active_tasks()
    for node in store.nodes.values():
        if node.name == node_name or not node.ready or not node.schedulable:
            continue
        room = room.plus(free(node, active))
    if not needed.fits_in(room):
        verdict.objections.append(
            f"evictees need {needed.cpu}m cpu, the rest of the fleet has "
            f"{room.cpu}m free"
        )
    return verdict


def upgrade_preflight(
    store: Store, gate: SkewGate, target_version: str
) -> Verdict:
    verdict = Verdict(operation=f"upgrade control plane to {target_version}")
    broken = violations(store)
    if broken:
        verdict.objections.append(
            f"cluster already inconsistent: {broken[0]}"
        )
    survives, why = survives_n_plus_one(store)
    if not survives:
        verdict.objections.append(f"no N+1 headroom: {why}")
    try:
        probe = SkewGate(
            control_plane=gate.control_plane,
            node_versions=dict(gate.node_versions),
        )
        probe.upgrade_control_plane(target_version)
    except Invalid as refused:
        verdict.objections.append(str(refused))
    return verdict
