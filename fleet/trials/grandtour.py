"""The grand tour: one cluster, every organ, and a checklist with numbers.

One continuous story: a manifest applies through the facade, the
engine places under a disruption budget, a node dies and its tasks
resettle, a rollout upgrades the fleet under the stall watch, a drain
is refused by the budget and a retire succeeds anyway, the journal
answers for a task's whole life, and the run closes with invariants,
conformance, and the phase table all ruling clean. Every subsystem
touched is asserted by number, because a tour that only waves at the
exhibits is a brochure.
"""

from __future__ import annotations

from fleet.api import Fleet
from fleet.conformance import Conformance
from fleet.manifest import gates_from, parse
from fleet.objects import Node, Resources
from fleet.phases import check_history
from fleet.roll.history import History
from fleet.roll.rolling import Roller
from fleet.timeline import phase_history
from fleet.trials.verdict import Verdict
from fleet.verify import violations


def run() -> Verdict:
    manifest = parse(
        {
            "deploys": [
                {"name": "web", "replicas": 4, "cpu": 300,
                 "labels": {"app": "web"}},
            ],
            "budgets": [
                {"name": "floor", "selector_key": "app",
                 "selector_value": "web", "min_available": 3},
            ],
        }
    )
    fleet = Fleet()
    _, fleet.guard = gates_from(manifest)
    for number in range(4):
        fleet.store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    for spec in manifest.deploys:
        fleet.apply_deploy("tour", spec)
    for _ in range(3):
        fleet.step()
    for task in fleet.store.tasks.values():
        if task.phase == "Bound":
            task.phase = "Running"
    placed_at_start = sum(
        1 for task in fleet.store.tasks.values() if task.phase == "Running"
    )

    lost_node = fleet.store.get_task("web-0").node
    moved = fleet.retire_node("tour", lost_node)
    for _ in range(3):
        fleet.step()
    for task in fleet.store.tasks.values():
        if task.phase == "Bound":
            task.phase = "Running"
    after_loss = sum(
        1 for task in fleet.store.tasks.values() if task.phase == "Running"
    )

    history = History(name="web")
    history.record(manifest.deploys[0].template, note="v1")
    history.record(manifest.deploys[0].template, note="v2")
    roller = Roller()
    roll = history.rollout(replicas=4, max_surge=1)
    steps = 0
    for _ in range(30):
        what = roller.step(fleet.store, roll)
        steps += 1
        for task in fleet.store.pending_tasks():
            fleet.engine.queue.offer(
                task.spec.name, task.spec.priority, task.spec.namespace
            )
        fleet.step()
        for task in fleet.store.tasks.values():
            if task.phase == "Bound":
                task.phase = "Running"
        if what == "done":
            break

    drain_home = next(iter(fleet.store.active_tasks())).node
    _, refused = fleet.drain("tour", drain_home)
    fleet.uncordon("tour", drain_home)

    some_task = sorted(
        task.spec.name for task in fleet.store.tasks.values()
    )[0]
    life = phase_history(fleet.engine.journal, fleet.store, some_task)
    life_legal = check_history(life) is None

    suite = Conformance()
    suite.run()

    numbers = {
        "placed_at_start": placed_at_start,
        "moved_by_retire": moved,
        "after_loss": after_loss,
        "rollout_steps": steps,
        "drain_refused_by_floor": len(refused),
        "life_checked": some_task,
        "life_legal": life_legal,
        "invariants_broken": len(violations(fleet.store)),
        "conformance_failing": len(suite.failing()),
    }
    holds = (
        placed_at_start == 4
        and moved >= 1
        and after_loss == 4
        and steps <= 12
        and len(refused) >= 1
        and life_legal
        and not violations(fleet.store)
        and not suite.failing()
    )
    return Verdict(
        trial="grandtour",
        sentence=(
            "manifest, engine, budget, node retirement, rollout, drain "
            "refusal, a legal life, clean invariants and twelve held "
            "promises in one continuous story: the tour asserts every "
            "exhibit by number because anything less is a brochure"
        ),
        numbers=numbers,
        holds=holds,
    )
