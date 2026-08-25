"""Two clusters, one placer: cluster picking is scheduling one level up.

The federator holds member clusters and places workloads by the same
grammar the node scheduler uses, filters then scores: a cluster passes
if it has the capacity and the required region, and among the passing
clusters the scorer picks. Failover is the same move as placement, a
re-pick excluding the failed member, and the two-level story is the
point: every hard question at the node tier reappears at the cluster
tier wearing a bigger hat.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Unschedulable
from fleet.objects import free
from fleet.store import Store


@dataclass
class Member:
    name: str
    region: str
    store: Store

    def headroom(self) -> int:
        active = self.store.active_tasks()
        return sum(
            free(node, active).cpu
            for node in self.store.nodes.values()
            if node.ready and node.schedulable
        )


@dataclass
class Federator:
    members: dict[str, Member] = field(default_factory=dict)
    placements: dict[str, str] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)

    def join(self, member: Member) -> None:
        self.members[member.name] = member

    def _passing(
        self, cpu: int, region: str | None, excluding: set[str]
    ) -> list[tuple[str, Member]]:
        reasons = {}
        passing = []
        for name, member in sorted(self.members.items()):
            if name in excluding:
                reasons[name] = "excluded"
                continue
            if region is not None and member.region != region:
                reasons[name] = f"region {member.region}, wanted {region}"
                continue
            room = member.headroom()
            if room < cpu:
                reasons[name] = f"headroom {room}m, wanted {cpu}m"
                continue
            passing.append((name, member))
        if not passing:
            raise Unschedulable(reasons)
        return passing

    def place(
        self,
        workload: str,
        cpu: int,
        region: str | None = None,
        excluding: set[str] | None = None,
    ) -> str:
        passing = self._passing(cpu, region, excluding or set())
        chosen = max(passing, key=lambda held: (held[1].headroom(), held[0]))
        self.placements[workload] = chosen[0]
        self.log.append(f"{workload} to {chosen[0]}")
        return chosen[0]

    def fail_over(self, workload: str, cpu: int, region: str | None = None) -> str:
        failed = self.placements.get(workload)
        excluding = {failed} if failed else set()
        chosen = self.place(workload, cpu, region, excluding)
        self.log.append(f"{workload} failed over from {failed} to {chosen}")
        return chosen
