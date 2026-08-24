"""Draining with a floor: the budget converts a dip into a slower drain.

Six web tasks over four nodes, floor of five. Draining a node all at
once evicts both of its tasks and running falls to four; the guarded
drain takes one, is refused the second, waits for the replacement to
land and takes the other on a later pass, so running never falls below
five. Same end state, different worst moment, and the worst moment is
the thing users experience.
"""

from __future__ import annotations

from fleet.control.budget import Budget, Guard
from fleet.control.deploy import DeploySpec
from fleet.objects import Resources, TaskSpec
from fleet.sim.cluster import Sim
from fleet.trials.verdict import Verdict


def _sim() -> Sim:
    sim = Sim()
    sim.add_nodes(4)
    sim.deploys.append(
        DeploySpec(
            name="web",
            replicas=6,
            template=TaskSpec(
                name="tpl",
                needs=Resources(cpu=300, memory=300),
                labels=(("app", "web"),),
            ),
        )
    )
    sim.run(5)
    return sim


def _drain_all_at_once(sim: Sim, node: str) -> int:
    worst = sim.running_count()
    for task in list(sim.store.active_tasks()):
        if task.node == node:
            generation = task.generation
            task.phase = "Pending"
            task.node = None
            sim.store.update_task(task, read_generation=generation)
    worst = min(worst, sim.running_count())
    sim.run(3)
    return worst


def _drain_with_floor(sim: Sim, node: str, floor: int) -> int:
    guard = Guard(
        budgets=[
            Budget(
                name="web-floor",
                selector_key="app",
                selector_value="web",
                min_available=floor,
            )
        ]
    )
    worst = sim.running_count()
    for _ in range(6):
        evicted, refused = guard.drain(sim.store, node)
        worst = min(worst, sim.running_count())
        sim.run(1)
        if not evicted and not refused:
            break
    return worst


def run() -> Verdict:
    rough = _sim()
    counts: dict[str, int] = {}
    for task in rough.store.active_tasks():
        counts[task.node] = counts.get(task.node, 0) + 1
    node = min(name for name, held in counts.items() if held == max(counts.values()))
    on_node = counts[node]
    rough_worst = _drain_all_at_once(rough, node)

    gentle = _sim()
    gentle_worst = _drain_with_floor(gentle, node, floor=5)

    numbers = {
        "tasks_on_drained_node": on_node,
        "worst_running_all_at_once": rough_worst,
        "worst_running_with_floor": gentle_worst,
        "end_running_either_way": gentle.running_count(),
    }
    holds = on_node == 2 and rough_worst == 4 and gentle_worst == 5
    return Verdict(
        trial="drainfloor",
        sentence=(
            "draining two tasks at once dips to 4 running; under a floor "
            "of 5 the second eviction is refused until the first "
            "replacement lands and the worst moment is 5, with both "
            "drains ending back at 6"
        ),
        numbers=numbers,
        holds=holds,
    )
