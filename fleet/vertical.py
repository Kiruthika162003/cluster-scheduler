"""Vertical right-sizing: requests learned from usage, plus the HPA fight.

The vertical scaler watches what a task actually uses and proposes a
request near the observed peak with headroom. Alone, it reclaims the
gap between asked and used. Sharing a deployment with the horizontal
scaler, the classic fight appears: shrinking the request raises the
utilisation ratio the horizontal scaler watches, which adds replicas,
which lowers per-replica usage, which invites another shrink. The
truce is scoping: vertical owns the request, horizontal owns the
count, and each watches a meter the other cannot move.
"""

from __future__ import annotations

from dataclasses import dataclass, field

HEADROOM = 1.2


@dataclass
class Sizer:
    window: int = 20
    seen: dict[str, list[int]] = field(default_factory=dict)
    proposals: dict[str, int] = field(default_factory=dict)

    def observe(self, task_name: str, used: int) -> None:
        samples = self.seen.setdefault(task_name, [])
        samples.append(used)
        if len(samples) > self.window:
            samples.pop(0)

    def propose(self, task_name: str, current_request: int) -> int:
        samples = self.seen.get(task_name, [])
        if len(samples) < self.window:
            return current_request
        peak = max(samples)
        sized = int(peak * HEADROOM)
        self.proposals[task_name] = sized
        return sized


def reclaim(current_request: int, proposal: int) -> int:
    return max(0, current_request - proposal)


@dataclass
class FightMeter:
    """Both scalers on one deployment, each move recorded."""

    request: int
    replicas: int
    total_load: float
    target_ratio: float = 0.7
    moves: list[str] = field(default_factory=list)

    def per_replica_use(self) -> float:
        return self.total_load / self.replicas

    def vertical_move(self) -> None:
        sized = int(self.per_replica_use() * HEADROOM)
        if sized != self.request:
            self.moves.append(f"request {self.request}->{sized}")
            self.request = sized

    def horizontal_move(self) -> None:
        ratio = self.per_replica_use() / self.request
        if ratio > self.target_ratio:
            self.moves.append(f"replicas {self.replicas}->{self.replicas + 1}")
            self.replicas += 1
        elif ratio < self.target_ratio / 2 and self.replicas > 1:
            self.moves.append(f"replicas {self.replicas}->{self.replicas - 1}")
            self.replicas -= 1

    def truce_move(self) -> None:
        """Size the request so the ratio lands exactly on the target."""
        sized = int(self.per_replica_use() / self.target_ratio)
        if sized != self.request:
            self.moves.append(f"request {self.request}->{sized}")
            self.request = sized

    def rounds(self, count: int, vertical: str = "off") -> int:
        for _ in range(count):
            if vertical == "private":
                self.vertical_move()
            elif vertical == "truce":
                self.truce_move()
            self.horizontal_move()
        return len(self.moves)
