"""Image locality: the pull you skip is the fastest pull there is.

Every node caches the images it has pulled; a task whose image is
already local starts immediately, and a cold task waits out the pull.
The locality scorer steers tasks toward nodes that already hold their
image, and the meters compare fleet-wide pull ticks and start latency
against a blind spread. The countervailing force is the same one as
always: locality concentrates, and the trial keeps the concentration
number next to the savings so neither is quoted alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.objects import Node, Task
from fleet.store import Store

PULL_TICKS = 8
IMAGE_LABEL = "image"


@dataclass
class ImageCaches:
    held: dict[str, set[str]] = field(default_factory=dict)
    pulls: int = 0
    pull_ticks_spent: int = 0

    def warm(self, node_name: str, image: str) -> None:
        self.held.setdefault(node_name, set()).add(image)

    def has(self, node_name: str, image: str) -> bool:
        return image in self.held.get(node_name, set())

    def start_delay(self, node_name: str, image: str) -> int:
        if self.has(node_name, image):
            return 0
        self.pulls += 1
        self.pull_ticks_spent += PULL_TICKS
        self.warm(node_name, image)
        return PULL_TICKS

    def locality_scorer(self, weight: float = 1.0):
        def score(task: Task, node: Node, active: list[Task]) -> float:
            del active
            image = task.spec.label_map().get(IMAGE_LABEL)
            if image is None:
                return 0.0
            return weight if self.has(node.name, image) else 0.0

        return score


def image_of(task: Task) -> str | None:
    return task.spec.label_map().get(IMAGE_LABEL)


def start_all(store: Store, caches: ImageCaches) -> dict[str, int]:
    """Charge every active task its start delay; per-task delays returned."""
    delays = {}
    for task in sorted(store.active_tasks(), key=lambda held: held.spec.name):
        image = image_of(task)
        if image is None or task.node is None:
            delays[task.spec.name] = 0
            continue
        delays[task.spec.name] = caches.start_delay(task.node, image)
    return delays
