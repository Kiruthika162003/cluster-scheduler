"""The burst lands at tick 10 either way; the balloons change who pays.

Four production tasks fill two nodes. A two-task critical burst arrives
at tick 10. Without balloons, preemption seats the burst instantly by
evicting two production tasks, which wait out a five tick node warmup
before running again: production dips to two for five ticks. With two
scavenger balloons submitted at tick 0, the full cluster benches them,
the pipeline-aware scaler provisions for them ahead of time, they
inflate onto the new node, and the burst pops exactly the balloons:
production never dips at all. The rent is the proactive node idling
under balloons for five ticks, and the receipt is a casualty list with
nobody on it.
"""

from __future__ import annotations

from fleet.autoscale import NodeScaler
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.balloon import BalloonFleet
from fleet.sched.placement import Engine
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _campaign(with_balloons: bool) -> dict:
    store = Store()
    for number in range(2):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    engine = Engine()
    scaler = NodeScaler(warmup=5, scale_down_after=100, pipeline_aware=True)
    for number in range(4):
        engine.submit(
            store,
            Task(
                spec=TaskSpec(
                    name=f"steady-{number}",
                    needs=Resources(cpu=500, memory=500),
                    priority=100,
                )
            ),
        )
    fleet = BalloonFleet(shape=Resources(cpu=500, memory=500), count=2)
    if with_balloons:
        fleet.submit(store, engine)
    steady_low = 4
    burst_landed = None
    for now in range(30):
        if now == 10:
            for number in range(2):
                engine.submit(
                    store,
                    Task(
                        spec=TaskSpec(
                            name=f"burst-{number}",
                            needs=Resources(cpu=500, memory=500),
                            priority=1500,
                        )
                    ),
                )
        engine.one_pass(store, now)
        stuck = len(store.pending_tasks())
        for name in scaler.observe_stuck(stuck, now):
            store.add_node(Node(name=name, capacity=Resources(cpu=1000, memory=1000)))
            engine.queue.shape_changed(now)
        if now >= 10:
            running_steady = sum(
                1
                for task in store.tasks.values()
                if task.spec.name.startswith("steady") and task.is_active()
            )
            steady_low = min(steady_low, running_steady)
            bursts = [
                store.tasks.get(f"burst-{number}") for number in range(2)
            ]
            if burst_landed is None and all(
                held is not None and held.is_active() for held in bursts
            ):
                burst_landed = now
    steady_displaced = sum(
        1
        for decision in engine.journal.decisions
        if decision.verb == "displace" and decision.subject.startswith("steady")
    )
    return {
        "burst_landed": burst_landed,
        "steady_low": steady_low,
        "steady_displaced": steady_displaced,
        "balloons_popped": fleet.popped_ever(engine),
        "nodes_provisioned": scaler.provisioned,
    }


def run() -> Verdict:
    bare = _campaign(with_balloons=False)
    insured = _campaign(with_balloons=True)

    numbers = {
        "burst_landed_either_way": (bare["burst_landed"], insured["burst_landed"]),
        "steady_low_bare": bare["steady_low"],
        "steady_low_insured": insured["steady_low"],
        "steady_displaced_bare": bare["steady_displaced"],
        "balloons_popped_insured": insured["balloons_popped"],
        "nodes": (bare["nodes_provisioned"], insured["nodes_provisioned"]),
    }
    holds = (
        bare["burst_landed"] == insured["burst_landed"] == 10
        and bare["steady_low"] == 2
        and insured["steady_low"] == 4
        and bare["steady_displaced"] == 2
        and insured["steady_displaced"] == 0
        and insured["balloons_popped"] == 2
    )
    return Verdict(
        trial="balloonpay",
        sentence=(
            "the burst lands at tick 10 with or without balloons because "
            "preemption is the latency insurance; the balloons change the "
            "casualty list, production dipping to 2 for the warmup bare "
            "and never dipping insured, with exactly the two balloons "
            "popped instead"
        ),
        numbers=numbers,
        holds=holds,
    )
