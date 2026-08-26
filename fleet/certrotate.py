"""Certificate rotation: two truths overlap so nothing breaks at midnight.

Rotation with a hard cutover is an outage scheduled by a calendar.
The rotator issues the next certificate while the old one still
verifies, and both stay valid through an overlap window; clients
re-pin during the overlap at their own pace. The laggard report
names clients still presenting the old certificate as the window
runs out, ordered by time remaining, because "3 clients will break
in 40 ticks, here are their names" is an actionable page and
"rotation at 80 percent" is not. Revocation is immediate and
separate from expiry: a leaked certificate dies now, overlap or no
overlap, and everything pinned to it breaks loudly rather than
trusting quietly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid, NotFound

LIFETIME = 100
OVERLAP = 20


@dataclass
class Certificate:
    serial: int
    issued_at: int
    expires_at: int
    revoked: bool = False

    def valid_at(self, tick: int) -> bool:
        return not self.revoked and self.issued_at <= tick < self.expires_at


@dataclass
class Rotator:
    certificates: dict[int, Certificate] = field(default_factory=dict)
    next_serial: int = 1
    pinned: dict[str, int] = field(default_factory=dict)

    def issue(self, now: int) -> Certificate:
        certificate = Certificate(
            serial=self.next_serial,
            issued_at=now,
            expires_at=now + LIFETIME,
        )
        self.certificates[certificate.serial] = certificate
        self.next_serial += 1
        return certificate

    def rotate(self, now: int) -> Certificate:
        current = self.current(now)
        if current is not None:
            current.expires_at = min(current.expires_at, now + OVERLAP)
        return self.issue(now)

    def current(self, now: int) -> Certificate | None:
        live = [
            certificate
            for certificate in self.certificates.values()
            if certificate.valid_at(now)
        ]
        if not live:
            return None
        return max(live, key=lambda certificate: certificate.serial)

    def revoke(self, serial: int) -> None:
        if serial not in self.certificates:
            raise NotFound(f"no certificate with serial {serial}")
        self.certificates[serial].revoked = True

    def pin(self, client: str, serial: int, now: int) -> None:
        certificate = self.certificates.get(serial)
        if certificate is None or not certificate.valid_at(now):
            raise Invalid(f"serial {serial} is not valid at {now}")
        self.pinned[client] = serial

    def verify(self, client: str, now: int) -> tuple[bool, str]:
        serial = self.pinned.get(client)
        if serial is None:
            return False, f"{client} presents no certificate"
        certificate = self.certificates[serial]
        if certificate.revoked:
            return False, f"serial {serial} is revoked"
        if not certificate.valid_at(now):
            return False, f"serial {serial} expired at {certificate.expires_at}"
        return True, f"serial {serial} verifies"

    def laggards(self, now: int) -> list[tuple[str, int]]:
        newest = self.current(now)
        if newest is None:
            return []
        rows = []
        for client, serial in self.pinned.items():
            if serial == newest.serial:
                continue
            held = self.certificates[serial]
            if held.revoked or not held.valid_at(now):
                remaining = 0
            else:
                remaining = held.expires_at - now
            rows.append((client, remaining))
        return sorted(rows, key=lambda row: (row[1], row[0]))

    def report(self, now: int) -> str:
        behind = self.laggards(now)
        newest = self.current(now)
        head = (
            f"serving serial {newest.serial}" if newest else "nothing valid"
        )
        if not behind:
            return f"{head}; every client is current"
        lines = [f"{head}; {len(behind)} laggard(s)"]
        for client, remaining in behind:
            state = (
                f"breaks in {remaining}" if remaining > 0 else "already broken"
            )
            lines.append(f"  {client}: {state}")
        return "\n".join(lines)
