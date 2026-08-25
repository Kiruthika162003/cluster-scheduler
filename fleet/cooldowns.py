"""Preemption cooldowns: the same task is not displaced twice in one breath.

A task that was just preempted and rescheduled is the cheapest victim
on its new node, so an unprotected fleet can walk one batch task
around the cluster like a pinball, each critical arrival displacing
it again. The cooldown grants a displaced task immunity for a window:
inside it, the preemptor must find another victim or refuse, and the
pinball count, how many times one task was displaced inside an hour,
is the meter that says whether the window is long enough.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PreemptionCooldowns:
    window: int
    displaced_at: dict[str, list[int]] = field(default_factory=dict)
    shielded: int = 0

    def note_displacement(self, task_name: str, now: int) -> None:
        self.displaced_at.setdefault(task_name, []).append(now)

    def immune(self, task_name: str, now: int) -> bool:
        history = self.displaced_at.get(task_name, [])
        recent = [tick for tick in history if now - tick < self.window]
        if recent:
            self.shielded += 1
            return True
        return False

    def pinball_count(self, task_name: str, span: int, now: int) -> int:
        return sum(
            1
            for tick in self.displaced_at.get(task_name, [])
            if 0 <= now - tick <= span
        )

    def worst_pinball(self, span: int, now: int) -> tuple[str, int] | None:
        counts = {
            name: self.pinball_count(name, span, now)
            for name in self.displaced_at
        }
        if not counts:
            return None
        name = max(counts, key=lambda held: (counts[held], held))
        return name, counts[name]
