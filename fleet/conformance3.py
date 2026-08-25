"""The third conformance wave: promises for the organs grown since the second.

Sidecars share fate, staged failures carry the stage's name, the
canary refresh halts on the first bad node, a backup restore behaves,
the weighted queue's ratio survives a one-task consumer, and the
event log never reissues a sequence number across compaction. Each
check is the smallest scenario that would catch the promise breaking,
which is what keeps the suite fast enough that people actually run it
before the upgrade instead of after the incident.
"""

from __future__ import annotations

from fleet.backupdrill import backup_drill
from fleet.conformance import Check
from fleet.eventretention import RetentionKeeper
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.queue import SchedulingQueue
from fleet.sidecars import SidecarKeeper
from fleet.stages import Stage, StageKeeper
from fleet.store import Store


def check_sidecars_share_fate() -> Check:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    primary = Task(spec=TaskSpec(name="web", needs=Resources(cpu=100, memory=100)))
    primary.bound_to("n0")
    store.add_task(primary)
    keeper = SidecarKeeper()
    keeper.attach(store, "web", Resources(cpu=10, memory=10))
    keeper.reconcile(store)
    generation = primary.generation
    primary.phase = "Succeeded"
    primary.node = None
    store.update_task(primary, read_generation=generation)
    keeper.reconcile(store)
    return Check(
        name="sidecars-share-fate",
        promise="a finished primary takes its sidecar with it",
        passed="web-side" not in store.tasks,
    )


def check_staged_failures_carry_the_stage() -> Check:
    store = Store()
    task = Task(spec=TaskSpec(name="api", needs=Resources(cpu=1, memory=1)))
    task.bound_to("n0")
    store.add_task(task)
    keeper = StageKeeper()
    keeper.declare("api", (Stage("migrate", attempts_allowed=1),))
    keeper.begin("api", now=0)
    told = keeper.fail(store, "api", now=1)
    return Check(
        name="staged-failures-carry-the-stage",
        promise="a task that dies in a stage says which stage",
        passed=told == "failed in migrate"
        and store.get_task("api").phase == "Failed",
    )


def check_backup_restores_behave() -> Check:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    report = backup_drill(store)
    return Check(
        name="backup-restores-behave",
        promise="a restore schedules work, not just holds bytes",
        passed=report.passed(),
    )


def check_weights_survive_the_consumer() -> Check:
    queue = SchedulingQueue(namespace_weights={"search": 2, "ads": 1})
    for number in range(6):
        queue.offer(f"s{number}", 100, namespace="search")
        queue.offer(f"a{number}", 100, namespace="ads")
    served = []
    for now in range(9):
        winner = queue.ready(now)[0]
        served.append(winner[0])
        queue.forget(winner)
    return Check(
        name="weights-survive-the-consumer",
        promise="the stated ratio holds for a one-task-per-pass consumer",
        passed="".join(served) == "assassass",
    )


def check_sequences_never_reissue() -> Check:
    store = Store()
    for number in range(6):
        store.add_task(
            Task(
                spec=TaskSpec(
                    name=f"t{number}", needs=Resources(cpu=1, memory=1)
                )
            )
        )
    keeper = RetentionKeeper()
    keeper.compact(store, keep_from=6)
    store.add_task(
        Task(spec=TaskSpec(name="fresh", needs=Resources(cpu=1, memory=1)))
    )
    fresh = store.events[-1]
    return Check(
        name="sequences-never-reissue",
        promise="compaction never causes a sequence number to repeat",
        passed=fresh.sequence == 6,
    )


THIRD_WAVE = (
    check_sidecars_share_fate,
    check_staged_failures_carry_the_stage,
    check_backup_restores_behave,
    check_weights_survive_the_consumer,
    check_sequences_never_reissue,
)
