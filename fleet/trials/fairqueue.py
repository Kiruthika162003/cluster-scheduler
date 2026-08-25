"""Equal priority, two teams, ten slots: the alphabet is not a policy.

Search and ads each submit ten equal-priority tasks toward a cluster
with room for nine. The plain queue breaks the tie by name and ads
takes the first nine slots whole, an allocation nobody chose, enforced
by a sort key. With namespace weights of two to one, the ready stream
deals two search for each ads inside the tied band and the nine slots
split six to three. The weight is policy an operator can defend in a
meeting; the alphabet was policy too, just nobody's.
"""

from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.placement import Engine
from fleet.sched.queue import SchedulingQueue
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _contest(weights: dict[str, int] | None) -> dict[str, int]:
    store = Store()
    for number in range(3):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=900, memory=900))
        )
    engine = Engine()
    if weights:
        engine.queue = SchedulingQueue(namespace_weights=weights)
    for number in range(10):
        for space in ("search", "ads"):
            engine.submit(
                store,
                Task(
                    spec=TaskSpec(
                        name=f"{space}-{number}",
                        needs=Resources(cpu=300, memory=300),
                        namespace=space,
                        priority=100,
                    )
                ),
            )
    engine.one_pass(store, now=0)
    placed = {"search": 0, "ads": 0}
    for task in store.active_tasks():
        placed[task.spec.namespace] += 1
    return placed


def run() -> Verdict:
    plain = _contest(None)
    weighted = _contest({"search": 2, "ads": 1})

    numbers = {
        "plain_split": plain,
        "weighted_split": weighted,
        "slots": 9,
    }
    holds = (
        plain == {"search": 0, "ads": 9}
        and weighted == {"search": 6, "ads": 3}
    )
    return Verdict(
        trial="fairqueue",
        sentence=(
            "the name tie hands ads all nine slots, an allocation nobody "
            "chose enforced by a sort key; weights of two to one split "
            "them six to three, which is a policy someone can defend"
        ),
        numbers=numbers,
        holds=holds,
    )
