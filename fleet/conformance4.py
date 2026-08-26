"""The fourth conformance wave: promises from the reliability organs.

The reserve never drains below its floor, scale-down waits out its
window, a stale fencing token cannot write, a convicted node loses
custody and earns it back, and the hotspot plan never creates the
hotspot it is fixing. Same rule as every wave: each check is the
smallest scenario that would catch the promise breaking.
"""

from __future__ import annotations

from fleet.apiratelimit import Bucket, Limiter
from fleet.conformance import Check
from fleet.hotspots import survey
from fleet.leaderelect import Election, FencedLog
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.quarantine import PROBATION, Warden
from fleet.scalerules import ScaleRules
from fleet.store import Store


def check_reserve_keeps_its_floor() -> Check:
    limiter = Limiter(reserve=Bucket(rate=0.1, burst=10), reserve_floor=2.0)
    limiter.register("noisy", rate=0.1, burst=1)
    for _ in range(30):
        limiter.allow("noisy", 0)
    return Check(
        name="reserve-keeps-its-floor",
        promise="a flood cannot drain the shared reserve below its floor",
        passed=limiter.reserve.level >= 2.0,
    )


def check_scaledown_waits() -> Check:
    rules = ScaleRules(stabilization=5)
    held = all(
        rules.decide(tick, current=8, desired=2) == 8 for tick in range(5)
    )
    released = rules.decide(5, current=8, desired=2) == 2
    return Check(
        name="scaledown-waits",
        promise="no replica leaves before the stabilization window passes",
        passed=held and released,
    )


def check_stale_tokens_bounce() -> Check:
    election = Election()
    log = FencedLog()
    old_token = election.campaign("old", now=0)
    new_token = election.campaign("new", now=100)
    log.write("new leader write", new_token)
    stale_landed = log.write("stale write", old_token)
    return Check(
        name="stale-tokens-bounce",
        promise="a write fenced by a newer token never lands",
        passed=not stale_landed and log.accepted == ["new leader write"],
    )


def check_conviction_and_parole() -> Check:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    warden = Warden()
    warden.task_died(store, "n0", "a-0", "a", now=0)
    warden.task_died(store, "n0", "b-0", "b", now=1)
    warden.task_died(store, "n0", "c-0", "c", now=2)
    convicted = not store.get_node("n0").schedulable
    warden.patrol(store, now=2 + PROBATION)
    paroled = store.get_node("n0").schedulable
    return Check(
        name="conviction-and-parole",
        promise="a killer node loses custody and a clean stint restores it",
        passed=convicted and paroled,
    )


def check_the_plan_makes_no_new_hotspot() -> Check:
    store = Store()
    for number in range(5):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    for index, cpu in enumerate((500, 200, 100, 100)):
        task = Task(
            spec=TaskSpec(name=f"h{index}", needs=Resources(cpu=cpu, memory=cpu))
        )
        task.bound_to("n0")
        store.add_task(task)
    for number in range(1, 5):
        task = Task(
            spec=TaskSpec(name=f"c{number}", needs=Resources(cpu=200, memory=200))
        )
        task.bound_to(f"n{number}")
        store.add_task(task)
    for move in survey(store)[0].moves:
        store.get_task(move.task).node = move.target
    return Check(
        name="the-plan-makes-no-new-hotspot",
        promise="applying the survey's moves leaves no hotspot behind",
        passed=survey(store) == [],
    )


FOURTH_WAVE = (
    check_reserve_keeps_its_floor,
    check_scaledown_waits,
    check_stale_tokens_bounce,
    check_conviction_and_parole,
    check_the_plan_makes_no_new_hotspot,
)
