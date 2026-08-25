"""Black Friday: bookings hold the line, balloons pop, spot fills the surge.

Run with: python -m examples.blackfriday
"""

from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.reservations import Broker
from fleet.sched.balloon import BalloonFleet
from fleet.sched.placement import Engine
from fleet.spot import SpotMarket, WorkTracker, evacuate, reclaim
from fleet.store import Store


def main() -> int:
    store = Store()
    for number in range(3):
        store.add_node(
            Node(name=f"perm-{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    engine = Engine()
    broker = Broker()

    broker.book(store, "checkout-surge", cpu=1200, starts=50, ends=80)
    allowed, why = broker.may_scale(store, cpu=2500, now=10)
    print(f"analytics asks for 2500m at tick 10: {'yes' if allowed else 'no'}, {why}")

    fleet = BalloonFleet(shape=Resources(cpu=600, memory=600), count=2)
    fleet.submit(store, engine)
    engine.one_pass(store, now=0)
    print(f"balloons inflated: {fleet.inflated(store)} holding checkout headroom")

    market = SpotMarket(reclaims={"spot-0": 70})
    store.add_node(Node(name="spot-0", capacity=Resources(cpu=1000, memory=1000)))
    tracker = WorkTracker()
    for number in range(2):
        name = f"batch-{number}"
        engine.submit(
            store,
            Task(
                spec=TaskSpec(
                    name=name, needs=Resources(cpu=450, memory=450), priority=10
                )
            ),
        )
        tracker.needed[name] = 30
    engine.one_pass(store, now=1)

    surge_landed = None
    for now in range(2, 100):
        if now == 50:
            for number in range(2):
                engine.submit(
                    store,
                    Task(
                        spec=TaskSpec(
                            name=f"checkout-{number}",
                            needs=Resources(cpu=600, memory=600),
                            priority=1500,
                        )
                    ),
                )
        for notice in market.tick(now):
            store.get_node(notice.node).schedulable = False
            evacuate(store, notice.node)
        for node in market.reclaimed_now(now):
            reclaim(store, tracker, node)
        for task in store.pending_tasks():
            engine.queue.offer(
                task.spec.name, task.spec.priority, task.spec.namespace
            )
        engine.one_pass(store, now)
        for task in store.tasks.values():
            if task.phase == "Bound":
                task.phase = "Running"
        tracker.advance(store)
        checkouts = [
            store.tasks.get(f"checkout-{number}") for number in range(2)
        ]
        if surge_landed is None and all(
            held is not None and held.phase == "Running" for held in checkouts
        ):
            surge_landed = now
    print(f"checkout surge running at tick {surge_landed}, balloons popped "
          f"{fleet.popped_ever(engine)}")
    print(f"spot reclaim: lost ticks {tracker.lost_ticks}, "
          f"batch finished {len(tracker.finished)} of 2")
    print(f"engine displaced {engine.displaced} tasks all night")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
