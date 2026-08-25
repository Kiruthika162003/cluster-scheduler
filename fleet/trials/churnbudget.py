"""A priority flood with and without a churn budget: the same work, spread out.

Six critical tasks arrive at once over a fleet fully occupied by batch.
Without a churn budget the engine displaces six batch tasks in a single
pass, an eviction storm the fleet's restart machinery meets all at
once. With a budget of two displacements per pass the same six land
over three passes, the deferred criticals benched with the reason in
the journal, and the batch evictions arrive in digestible pairs. Total
work is identical; the budget spreads the pain without changing the
outcome, which is what pacing knobs are actually for, and this one,
unlike the rollout's, is connected.
"""

from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.placement import Engine
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _flood(max_per_pass: int) -> tuple[Engine, list[int]]:
    store = Store()
    for number in range(6):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    engine = Engine(max_displacements_per_pass=max_per_pass)
    for number in range(6):
        engine.submit(
            store,
            Task(
                spec=TaskSpec(
                    name=f"batch-{number}",
                    needs=Resources(cpu=900, memory=900),
                    priority=10,
                )
            ),
        )
    engine.one_pass(store, now=0)
    for number in range(6):
        engine.submit(
            store,
            Task(
                spec=TaskSpec(
                    name=f"crit-{number}",
                    needs=Resources(cpu=900, memory=900),
                    priority=1500,
                )
            ),
        )
    per_pass = []
    for now in range(1, 40):
        before = engine.displaced
        engine.one_pass(store, now)
        per_pass.append(engine.displaced - before)
        if all(
            store.tasks[f"crit-{number}"].is_active() for number in range(6)
        ):
            break
    return engine, [count for count in per_pass if count]


def run() -> Verdict:
    storm_engine, storm_waves = _flood(max_per_pass=10**9)
    paced_engine, paced_waves = _flood(max_per_pass=2)

    numbers = {
        "waves_unbudgeted": storm_waves,
        "waves_budgeted": paced_waves,
        "total_displaced_each": (storm_engine.displaced, paced_engine.displaced),
        "deferrals_recorded": paced_engine.churn_deferred,
    }
    holds = (
        storm_waves == [6]
        and paced_waves == [2, 2, 2]
        and storm_engine.displaced == paced_engine.displaced == 6
        and paced_engine.churn_deferred > 0
    )
    return Verdict(
        trial="churnbudget",
        sentence=(
            "the unbudgeted flood evicts six batch tasks in one pass; the "
            "budget of two spreads the same six over three passes with "
            "the deferrals journalled, identical totals, digestible waves"
        ),
        numbers=numbers,
        holds=holds,
    )
