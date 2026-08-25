"""Cordon leases: the forgotten cordon is a capacity leak with a name on it.

Every cordon is placed for a reason and forgotten for none. The lease
sweeper records who cordoned what and when, expires cordons past their
lease unless they were renewed, and reports the standing ones oldest
first, because the cordon somebody placed three weeks ago for a
maintenance that finished in an hour is the most common way a fleet
quietly loses a machine. Expiry is polite: it uncordons and journals,
never deletes, since the node was fine all along.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.audit import Journal
from fleet.store import Store


@dataclass
class CordonLease:
    node: str
    who: str
    reason: str
    placed_at: int
    expires_at: int


@dataclass
class CordonLeases:
    default_ttl: int = 50
    leases: dict[str, CordonLease] = field(default_factory=dict)
    expired: int = 0

    def cordon(
        self,
        store: Store,
        journal: Journal,
        node_name: str,
        who: str,
        reason: str,
        now: int,
        ttl: int | None = None,
    ) -> None:
        node = store.get_node(node_name)
        node.schedulable = False
        self.leases[node_name] = CordonLease(
            node=node_name,
            who=who,
            reason=reason,
            placed_at=now,
            expires_at=now + (ttl if ttl is not None else self.default_ttl),
        )
        journal.note(now, who, node_name, "cordon", reason)

    def renew(self, node_name: str, now: int, ttl: int | None = None) -> None:
        lease = self.leases[node_name]
        lease.expires_at = now + (ttl if ttl is not None else self.default_ttl)

    def sweep(self, store: Store, journal: Journal, now: int) -> list[str]:
        released = []
        for name, lease in sorted(self.leases.items()):
            if lease.expires_at > now:
                continue
            node = store.nodes.get(name)
            if node is not None:
                node.schedulable = True
            journal.note(
                now,
                "cordon-leases",
                name,
                "uncordon",
                f"lease from {lease.who} expired, was: {lease.reason}",
            )
            del self.leases[name]
            self.expired += 1
            released.append(name)
        return released

    def standing(self, now: int) -> list[str]:
        return [
            f"{lease.node}: {lease.who}, {lease.reason}, "
            f"held {now - lease.placed_at}"
            for lease in sorted(
                self.leases.values(), key=lambda held: held.placed_at
            )
        ]
