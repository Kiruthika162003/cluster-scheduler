"""Background scrubbing: corruption found on schedule, not on read.

A corrupt block discovered by the read that needed it is an outage;
the same block found by a background scrub is a work order. The
scrubber walks every block on a cycle, verifying a bounded number
per tick so the foreground never feels it, and the cycle time is
the honest metric: blocks over rate is the fastest any corruption
can be promised to surface, and doubling the fleet without raising
the rate silently doubles that promise. Found corruption goes to a
repair queue with the scan timestamp, because mean-time-to-detect
is only computable if detection is stamped, and the rate planner
inverts the arithmetic: name the detection promise, get the rate
the fleet must sustain.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass
class Scrubber:
    blocks: list[str]
    rate: int
    cursor: int = 0
    verified: int = 0
    corrupt: set[str] = field(default_factory=set)
    repair_queue: list[tuple[str, int]] = field(default_factory=list)
    cycles_completed: int = 0

    def __post_init__(self) -> None:
        if not self.blocks:
            raise Invalid("a scrubber with no blocks guards nothing")
        if self.rate <= 0:
            raise Invalid("the scrub rate must be positive")

    def mark_corrupt(self, block: str) -> None:
        if block not in self.blocks:
            raise Invalid(f"{block} is not on this scrubber's walk")
        self.corrupt.add(block)

    def tick(self, now: int) -> list[str]:
        found = []
        for _ in range(self.rate):
            block = self.blocks[self.cursor]
            self.verified += 1
            if block in self.corrupt:
                self.corrupt.discard(block)
                self.repair_queue.append((block, now))
                found.append(block)
            self.cursor += 1
            if self.cursor == len(self.blocks):
                self.cursor = 0
                self.cycles_completed += 1
        return found

    def cycle_ticks(self) -> int:
        return -(-len(self.blocks) // self.rate)

    def detection_promise(self) -> str:
        return (
            f"any corruption surfaces within {self.cycle_ticks()} ticks "
            f"({len(self.blocks)} blocks at {self.rate}/tick)"
        )


def rate_for_promise(block_count: int, within_ticks: int) -> int:
    if block_count <= 0 or within_ticks <= 0:
        raise Invalid("the promise needs positive blocks and ticks")
    return -(-block_count // within_ticks)
