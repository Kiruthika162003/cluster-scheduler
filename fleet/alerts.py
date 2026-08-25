"""Alert shaping: the pager's job is to be believed, so it must not babble.

Raw events become pages through two filters. Dedup folds identical
alerts inside a window into one page with a count; flap suppression
notices a subject alternating firing and clearing and replaces the
stream with one flapping page and one final steady-state page. The
meter that matters is pages per incident, because every page past the
first that says the same thing spends the on-call's belief, and belief
is the only currency a pager holds.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Event:
    tick: int
    subject: str
    state: str


@dataclass
class Pager:
    dedup_window: int = 10
    flap_threshold: int = 3
    pages: list[str] = field(default_factory=list)
    last_paged: dict[tuple[str, str], int] = field(default_factory=dict)
    folded: int = 0
    transitions: dict[str, int] = field(default_factory=dict)
    flapping: set[str] = field(default_factory=set)
    last_state: dict[str, str] = field(default_factory=dict)

    def take(self, event: Event) -> None:
        before = self.last_state.get(event.subject)
        self.last_state[event.subject] = event.state
        if before is not None and before != event.state:
            self.transitions[event.subject] = (
                self.transitions.get(event.subject, 0) + 1
            )
            if (
                self.transitions[event.subject] >= self.flap_threshold
                and event.subject not in self.flapping
            ):
                self.flapping.add(event.subject)
                self.pages.append(
                    f"[{event.tick}] {event.subject} is flapping, "
                    f"{self.transitions[event.subject]} transitions; "
                    f"suppressing until it settles"
                )
                return
        if event.subject in self.flapping:
            self.folded += 1
            return
        key = (event.subject, event.state)
        last = self.last_paged.get(key)
        if last is not None and event.tick - last < self.dedup_window:
            self.folded += 1
            return
        self.last_paged[key] = event.tick
        self.pages.append(f"[{event.tick}] {event.subject} {event.state}")

    def settle(self, subject: str, tick: int) -> None:
        """The flap ended; one page tells the final truth."""
        if subject in self.flapping:
            self.flapping.discard(subject)
            self.transitions[subject] = 0
            state = self.last_state.get(subject, "unknown")
            self.pages.append(
                f"[{tick}] {subject} settled: {state}"
            )
