"""Autoscaling: the replica dial follows load, the node dial follows replicas.

The horizontal scaler moves a deployment's replica count toward observed
load over capacity, damped and bounded, because an undamped scaler is an
oscillator with a service attached. The cluster scaler watches for tasks
that stay unschedulable and provisions nodes after a warmup delay, then
retires nodes that have sat empty. Both dials keep their reasoning as
numbers, not adjectives.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PER_REPLICA = 100.0
TARGET = 0.7


@dataclass
class ReplicaScaler:
    floor: int
    ceiling: int
    step_limit: int = 4
    tolerance: int = 0
    decisions: list[tuple[int, int]] = field(default_factory=list)

    def wanted(self, current: int, load: float) -> int:
        raw = load / (PER_REPLICA * TARGET)
        target = max(self.floor, min(self.ceiling, round(raw + 0.5)))
        if abs(target - current) <= self.tolerance:
            self.decisions.append((current, current))
            return current
        step = max(-self.step_limit, min(self.step_limit, target - current))
        chosen = current + step
        self.decisions.append((current, chosen))
        return chosen


@dataclass
class NodeScaler:
    warmup: int = 5
    scale_down_after: int = 12
    provisioning: dict[str, int] = field(default_factory=dict)
    empty_since: dict[str, int] = field(default_factory=dict)
    provisioned: int = 0
    retired: int = 0

    def observe_stuck(self, stuck: int, now: int) -> list[str]:
        """Order one node per call while anything is stuck; names returned
        when their warmup completes."""
        if stuck > 0:
            name = f"auto-{self.provisioned + len(self.provisioning)}"
            if name not in self.provisioning:
                self.provisioning[name] = now + self.warmup
        arrived = []
        for name, ready_at in sorted(self.provisioning.items()):
            if now >= ready_at:
                arrived.append(name)
        for name in arrived:
            del self.provisioning[name]
            self.provisioned += 1
        return arrived

    def observe_empty(self, empty_nodes: list[str], now: int) -> list[str]:
        """Nodes empty long enough to retire, hysteresis applied."""
        for name in empty_nodes:
            self.empty_since.setdefault(name, now)
        for name in list(self.empty_since):
            if name not in empty_nodes:
                del self.empty_since[name]
        retiring = [
            name
            for name, since in self.empty_since.items()
            if now - since >= self.scale_down_after
        ]
        for name in retiring:
            del self.empty_since[name]
            self.retired += 1
        return sorted(retiring)
