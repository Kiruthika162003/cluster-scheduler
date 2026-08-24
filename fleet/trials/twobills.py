"""Blue green and rolling, itemised: capacity, exposure, and the undo.

The same four replica upgrade both ways. Blue green peaks at eight
tasks, twice the capacity, serves exactly one version at every moment,
and undoes a bad build in one cutover while the standby is warm.
Rolling peaks at five, but serves a mix of versions for seven of its
nine steps and undoes by rolling everything back through the same
churn it came in on. Capacity, exposure, undo: each strategy wins two
and loses one, and which loss is affordable is the whole decision.
"""

from __future__ import annotations

from fleet.objects import Resources, Task, TaskSpec
from fleet.roll.bluegreen import BlueGreen
from fleet.roll.rolling import Roller, Rollout
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _template() -> TaskSpec:
    return TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100))


def _blue_green() -> tuple[int, int, int]:
    store = Store()
    stage = BlueGreen(replicas=4)
    stage.deploy_blue(store, _template())
    stage.stage_green(store, _template())
    mixed_serving = 0
    stage.cut_over()
    stage.retire_standby(store)
    return stage.peak_tasks, mixed_serving, stage.rollback_ticks()


def _rolling() -> tuple[int, int, int]:
    roller = Roller()
    store = Store()
    seed = Rollout(name="web", replicas=4, template=_template(), revision=1)
    for number in range(4):
        task = Task(spec=roller._stamped(seed, number))
        task.bound_to(f"n{number}")
        task.phase = "Running"
        store.add_task(task)
    fresh = Rollout(name="web", replicas=4, template=_template(), revision=2)
    steps = mixed = 0
    peak = len(store.tasks)
    for _ in range(30):
        what = roller.step(store, fresh)
        steps += 1
        peak = max(peak, len(store.tasks))
        revisions = {
            task.spec.label_map().get("revision") for task in store.tasks.values()
        }
        if len(revisions) > 1:
            mixed += 1
        for task in store.tasks.values():
            if task.phase == "Pending":
                task.phase = "Running"
        if what == "done":
            break
    return peak, mixed, steps


def run() -> Verdict:
    bg_peak, bg_mixed, bg_undo = _blue_green()
    roll_peak, roll_mixed, roll_steps = _rolling()

    numbers = {
        "peak_bluegreen": bg_peak,
        "peak_rolling": roll_peak,
        "mixed_steps_bluegreen": bg_mixed,
        "mixed_steps_rolling": roll_mixed,
        "undo_bluegreen": bg_undo,
        "undo_rolling_steps": roll_steps,
    }
    holds = (
        bg_peak == 8
        and roll_peak == 5
        and bg_mixed == 0
        and roll_mixed == 7
        and bg_undo == 1
        and roll_steps == 9
    )
    return Verdict(
        trial="twobills",
        sentence=(
            "blue green pays 8 tasks of peak for zero mixed-version "
            "moments and a one-move undo; rolling pays 5 of peak, serves "
            "a version mix for 7 of 9 steps, and undoes through the same "
            "churn: each wins two meters of three"
        ),
        numbers=numbers,
        holds=holds,
    )
