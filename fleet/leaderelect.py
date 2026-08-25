"""Leader election: one controller acts, the rest watch the lease.

Two copies of a controller both stepping the same rollout double
every surge, so exactly one may act and the lease decides which. A
candidate acquires the lease if it is vacant or expired, renews it
while healthy, and steps down by letting it lapse. Every acquisition
mints a fencing token one higher than the last, and actions carry
the token: a store that has seen token 7 refuses token 6, which is
what turns "the old leader woke up and kept writing" from a
corruption into a log line. The lease answers who leads; the token
answers whether a straggler's write is still welcome, and the second
question is the one that saves the data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

LEASE_TICKS = 10


@dataclass
class Lease:
    holder: str
    token: int
    renewed_at: int

    def expired(self, now: int) -> bool:
        return now - self.renewed_at >= LEASE_TICKS


@dataclass
class Election:
    lease: Lease | None = None
    handovers: list[str] = field(default_factory=list)

    def campaign(self, candidate: str, now: int) -> int | None:
        """Returns the fencing token on victory, None while another leads."""
        if self.lease is None or self.lease.expired(now):
            token = (self.lease.token + 1) if self.lease else 1
            before = self.lease.holder if self.lease else "nobody"
            self.lease = Lease(holder=candidate, token=token, renewed_at=now)
            self.handovers.append(
                f"[{now}] {before} -> {candidate} (token {token})"
            )
            return token
        if self.lease.holder == candidate:
            self.lease.renewed_at = now
            return self.lease.token
        return None

    def resign(self, candidate: str, now: int) -> bool:
        if self.lease is not None and self.lease.holder == candidate:
            self.lease.renewed_at = now - LEASE_TICKS
            return True
        return False

    def leader(self, now: int) -> str | None:
        if self.lease is None or self.lease.expired(now):
            return None
        return self.lease.holder


@dataclass
class FencedLog:
    """The write side of the bargain: stale tokens bounce."""

    highest_seen: int = 0
    accepted: list[str] = field(default_factory=list)
    fenced: list[str] = field(default_factory=list)

    def write(self, entry: str, token: int) -> bool:
        if token < self.highest_seen:
            self.fenced.append(f"{entry} (token {token} < {self.highest_seen})")
            return False
        self.highest_seen = token
        self.accepted.append(entry)
        return True


@dataclass
class Controller:
    name: str
    election: Election
    log: FencedLog
    token: int | None = None
    acted: int = 0

    def tick(self, now: int, work: str | None = None) -> str:
        won = self.election.campaign(self.name, now)
        if won is None:
            self.token = None
            return "standby"
        self.token = won
        if work is None:
            return "leading"
        if self.log.write(work, self.token):
            self.acted += 1
            return f"did {work}"
        return "fenced off"
