"""Volumes: data has a home, and the home outvotes every scorer.

A claim binds a task to data that lives on one node. The filter refuses
every other node, whatever the scorers prefer, because moving a task is
one write and moving its data is all of them. Migration exists but is
priced in copy-ticks proportional to the volume, and the trial measures
what data gravity does to a spread policy: the tasks pile up where
their volumes are, and the scorer watches, outvoted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid, NotFound
from fleet.objects import Node, Task


@dataclass
class Volume:
    name: str
    size: int
    home: str
    copies_in_flight: int = 0


@dataclass
class VolumeBook:
    volumes: dict[str, Volume] = field(default_factory=dict)
    claims: dict[str, str] = field(default_factory=dict)
    migrations: list[tuple[str, str, str, int]] = field(default_factory=list)

    def add(self, volume: Volume) -> None:
        if volume.name in self.volumes:
            raise Invalid(f"volume {volume.name} exists")
        self.volumes[volume.name] = volume

    def claim(self, task_name: str, volume_name: str) -> None:
        if volume_name not in self.volumes:
            raise NotFound(f"volume {volume_name}")
        held = self.claims.get(task_name)
        if held is not None and held != volume_name:
            raise Invalid(f"{task_name} already claims {held}")
        self.claims[task_name] = volume_name

    def home_of(self, task_name: str) -> str | None:
        volume_name = self.claims.get(task_name)
        if volume_name is None:
            return None
        return self.volumes[volume_name].home

    def gravity_filter(self):
        """A filter closed over the book, shaped like every other filter."""

        def check(task: Task, node: Node, active: list[Task]) -> str | None:
            del active
            home = self.home_of(task.spec.name)
            if home is None or home == node.name:
                return None
            return f"volume lives on {home}"

        return check

    def migrate(self, volume_name: str, to: str, copy_rate: int = 100) -> int:
        """Move a volume; returns the copy-ticks the move costs."""
        volume = self.volumes.get(volume_name)
        if volume is None:
            raise NotFound(f"volume {volume_name}")
        if volume.home == to:
            return 0
        ticks = (volume.size + copy_rate - 1) // copy_rate
        self.migrations.append((volume_name, volume.home, to, ticks))
        volume.home = to
        return ticks
