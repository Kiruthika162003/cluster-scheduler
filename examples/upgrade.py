"""An upgrade with a bad build in the middle: canary, rollback, retry.

Run with: python -m examples.upgrade
"""

from __future__ import annotations

from fleet.objects import Resources, Task, TaskSpec
from fleet.roll.canary import Canary
from fleet.roll.history import History
from fleet.roll.rolling import Roller
from fleet.store import Store


def template(tag: str) -> TaskSpec:
    return TaskSpec(
        name="tpl", needs=Resources(cpu=100, memory=100), labels=(("build", tag),)
    )


def roll_out(store: Store, roller: Roller, roll) -> None:
    for _ in range(30):
        what = roller.step(store, roll)
        for task in store.tasks.values():
            if task.phase == "Pending":
                task.phase = "Running"
        if what == "done":
            break


def main() -> int:
    history = History(name="api")
    roller = Roller()
    store = Store()

    history.record(template("v1"), note="initial")
    first = history.rollout(replicas=4)
    for ordinal in range(4):
        task = Task(spec=roller._stamped(first, ordinal))
        task.bound_to(f"n{ordinal}")
        task.phase = "Running"
        store.add_task(task)

    history.record(template("v2-bad"), note="the friday build")
    watcher = Canary(traffic_share=0.10)
    while watcher.state == "watching":
        watcher.tick(2000, stable_error_rate=0.005, canary_error_rate=0.12)
    print(f"canary verdict on v2: {watcher.state}")

    if watcher.state == "rollback":
        back = history.rollback_to(1, replicas=4)
        roll_out(store, roller, back)
        print(f"rolled back under revision {back.revision}: {history.current().note}")

    builds = sorted({task.spec.label_map()["build"] for task in store.tasks.values()})
    print(f"builds running now: {builds}")

    history.record(template("v2-fixed"), note="the monday build")
    fixed = history.rollout(replicas=4)
    roll_out(store, roller, fixed)
    builds = sorted({task.spec.label_map()["build"] for task in store.tasks.values()})
    print(f"after the fixed build: {builds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
