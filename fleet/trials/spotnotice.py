"""The reclaim notice is worth 21 ticks, but only with a cordon attached.

Eight thirty-tick jobs run on two stable and two spot nodes; the spot
nodes are reclaimed at ticks 20 and 35 with four ticks of warning. The
fleet that ignores its notices loses 50 ticks of progress across 4
mid-flight kills and finishes at tick 64. The first reactive draft
evacuated on notice and measured identical losses, because the
scheduler calmly re-placed the evacuees onto the same doomed node: an
evacuation without a cordon is a suggestion. Cordon plus evacuate loses
zero ticks, reruns nothing, and finishes at 43.
"""

from __future__ import annotations

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.spot import SpotMarket, WorkTracker, evacuate, reclaim
from fleet.store import Store
from fleet.trials.verdict import Verdict


def _campaign(reactive: bool) -> tuple[int, WorkTracker]:
    store = Store()
    for number in range(2):
        store.add_node(
            Node(name=f"stable-{number}", capacity=Resources(cpu=1000, memory=1000))
        )
        store.add_node(
            Node(name=f"spot-{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    market = SpotMarket(reclaims={"spot-0": 20, "spot-1": 35})
    tracker = WorkTracker()
    scheduler = Scheduler()
    for number in range(8):
        task = Task(
            spec=TaskSpec(
                name=f"job-{number}", needs=Resources(cpu=450, memory=450)
            )
        )
        store.add_task(task)
        tracker.needed[task.spec.name] = 30
    finished_at = -1
    for now in range(200):
        for notice in market.tick(now):
            if reactive:
                store.get_node(notice.node).schedulable = False
                evacuate(store, notice.node)
        for node in market.reclaimed_now(now):
            reclaim(store, tracker, node)
        scheduler.schedule_pending(store)
        for task in store.tasks.values():
            if task.phase == "Bound":
                task.phase = "Running"
        tracker.advance(store)
        if len(tracker.finished) == 8:
            finished_at = now
            break
    return finished_at, tracker


def run() -> Verdict:
    deaf_done, deaf = _campaign(reactive=False)
    alert_done, alert = _campaign(reactive=True)

    numbers = {
        "finished_ignoring": deaf_done,
        "lost_ticks_ignoring": deaf.lost_ticks,
        "reruns_ignoring": deaf.reruns,
        "finished_reactive": alert_done,
        "lost_ticks_reactive": alert.lost_ticks,
        "reruns_reactive": alert.reruns,
    }
    holds = (
        deaf_done == 64
        and deaf.lost_ticks == 50
        and deaf.reruns == 4
        and alert_done == 43
        and alert.lost_ticks == 0
        and alert.reruns == 0
    )
    return Verdict(
        trial="spotnotice",
        sentence=(
            "ignoring reclaim notices costs 50 lost ticks, 4 reruns and "
            "finishes at 64; cordon plus evacuate on the same notices "
            "loses nothing and finishes at 43, and without the cordon the "
            "scheduler re-places evacuees onto the doomed node"
        ),
        numbers=numbers,
        holds=holds,
    )
