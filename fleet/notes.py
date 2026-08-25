"""Operator notes: the context that otherwise lives in one person's head.

A note pins a sentence to an object with an author and an expiry,
because context rots: the note that said ignore the n3 alerts, disk
swap Tuesday is correct for a week and misleading forever after. Live
notes surface wherever their object appears; expired notes vanish from
pages but stay in the ledger, since the review sometimes needs to know
what the on-call believed at the time.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Note:
    subject: str
    author: str
    text: str
    written_at: int
    expires_at: int

    def live(self, now: int) -> bool:
        return now < self.expires_at

    def line(self) -> str:
        return f"{self.subject}: {self.text} ({self.author})"


@dataclass
class Noteboard:
    notes: list[Note] = field(default_factory=list)

    def pin(
        self, subject: str, author: str, text: str, now: int, ttl: int = 100
    ) -> Note:
        note = Note(
            subject=subject,
            author=author,
            text=text,
            written_at=now,
            expires_at=now + ttl,
        )
        self.notes.append(note)
        return note

    def about(self, subject: str, now: int) -> list[Note]:
        return [
            note
            for note in self.notes
            if note.subject == subject and note.live(now)
        ]

    def live_notes(self, now: int) -> list[Note]:
        return [note for note in self.notes if note.live(now)]

    def believed_at(self, subject: str, when: int) -> list[Note]:
        """What the on-call had pinned at a past moment, for the review."""
        return [
            note
            for note in self.notes
            if note.subject == subject
            and note.written_at <= when < note.expires_at
        ]
