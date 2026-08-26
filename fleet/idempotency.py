"""Idempotency keys: a retried request must land exactly once.

A client that times out cannot know whether its request landed, so
it retries, and without protection the fleet scales twice for one
intent. The key store remembers each idempotency key with the
response it produced: a replay returns the remembered response,
byte for byte, without re-running anything. The dangerous window
is in-progress, after the first attempt began and before it
finished; a replay arriving there is told to wait rather than run,
because running it is a duplicate and failing it teaches clients
to stop sending keys. Keys expire so the store is not a second
database, and an expired replay runs fresh, which is the honest
trade: idempotency has a horizon and the horizon is printed on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Conflict, Invalid

KEY_TTL = 500


@dataclass
class Remembered:
    response: str | None
    began_at: int
    finished_at: int | None = None


@dataclass
class KeyStore:
    entries: dict[str, Remembered] = field(default_factory=dict)
    replays_served: int = 0
    duplicates_prevented: int = 0

    def _sweep(self, now: int) -> None:
        expired = [
            key
            for key, entry in self.entries.items()
            if entry.finished_at is not None
            and now - entry.finished_at >= KEY_TTL
        ]
        for key in expired:
            del self.entries[key]

    def begin(self, key: str, now: int) -> str:
        if not key:
            raise Invalid("an empty idempotency key protects nothing")
        self._sweep(now)
        entry = self.entries.get(key)
        if entry is None:
            self.entries[key] = Remembered(response=None, began_at=now)
            return "run"
        if entry.finished_at is None:
            self.duplicates_prevented += 1
            return "wait: the first attempt is still running"
        self.replays_served += 1
        return f"replay: {entry.response}"

    def finish(self, key: str, response: str, now: int) -> None:
        entry = self.entries.get(key)
        if entry is None:
            raise Invalid(f"{key} never began")
        if entry.finished_at is not None:
            raise Conflict(f"{key} already finished")
        entry.response = response
        entry.finished_at = now

    def abandon(self, key: str) -> None:
        """A crashed attempt releases the key so a retry can run."""
        entry = self.entries.get(key)
        if entry is None or entry.finished_at is not None:
            raise Invalid(f"{key} is not in progress")
        del self.entries[key]

    def meter(self) -> str:
        return (
            f"{self.replays_served} replays served, "
            f"{self.duplicates_prevented} duplicates prevented"
        )
