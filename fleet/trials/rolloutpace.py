"""Rollout pacing: surge buys speed with capacity, unavailability with risk.

The same three-replica rollout runs under three settings: surge 1 and no
unavailability allowed, surge 3, and surge 0 with one unavailable
allowed. The meters are steps to done and the worst running count on the
way. Surge pays for speed with spare capacity; maxUnavailable pays with
user-visible headroom; the default pays with time. Nobody pays nothing.
"""

from __future__ import annotations

from fleet.objects import Resources, Task, TaskSpec
from fleet.roll.rolling import Roller, Rollout
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _template() -> TaskSpec:
    return TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100))


def _seeded(roller: Roller, count: int = 3) -> Store:
    store = Store()
    seed = Rollout(name="web", replicas=count, template=_template(), revision=1)
    for ordinal in range(count):
        task = Task(spec=roller._stamped(seed, ordinal))
        task.bound_to(f"n{ordinal}")
        task.phase = "Running"
        store.add_task(task)
    return store


def _run(max_surge: int, max_unavailable: int) -> tuple[int, int]:
    roller = Roller()
    store = _seeded(roller)
    roll = Rollout(
        name="web",
        replicas=3,
        template=_template(),
        revision=2,
        max_surge=max_surge,
        max_unavailable=max_unavailable,
    )
    steps = 0
    worst = 3
    for _ in range(40):
        what = roller.step(store, roll)
        steps += 1
        running = sum(1 for t in store.tasks.values() if t.phase == "Running")
        worst = min(worst, running)
        for task in store.tasks.values():
            if task.phase == "Pending":
                task.phase = "Running"
        if what == "done":
            break
    return steps, worst


def run() -> Verdict:
    slow_steps, slow_worst = _run(max_surge=1, max_unavailable=0)
    wide_steps, wide_worst = _run(max_surge=3, max_unavailable=0)
    dip_steps, dip_worst = _run(max_surge=0, max_unavailable=1)

    numbers = {
        "steps_surge1": slow_steps,
        "worst_surge1": slow_worst,
        "steps_surge3": wide_steps,
        "worst_surge3": wide_worst,
        "steps_dip1": dip_steps,
        "worst_dip1": dip_worst,
    }
    holds = (
        slow_steps == 7
        and slow_worst == 3
        and wide_steps == 7
        and wide_worst == 3
        and dip_steps == 7
        and dip_worst == 2
    )
    return Verdict(
        trial="rolloutpace",
        sentence=(
            "surge 1 and surge 3 both finish in 7 steps holding 3 running "
            "because each step does one thing regardless of headroom, and "
            "maxUnavailable 1 finishes in the same 7 steps dipping to 2: "
            "in this engine the pacing knobs move the dip, not the clock"
        ),
        numbers=numbers,
        holds=holds,
    )
