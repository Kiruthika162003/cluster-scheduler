"""The conformance suite: what any fleet worth the name must be able to say.

Each check is a tiny scenario run against the real components with a
sentence for what conformance means there. The suite exists apart from
the unit tests because it answers a different question: not does each
piece work, but does the assembled system still honour the promises an
operator relies on. A conforming fleet passes every check; the report
names any it fails in the operator's language, not the test runner's.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.control.budget import Budget, Guard
from fleet.control.deploy import Deployer, DeploySpec
from fleet.control.nodes import EVICT_AFTER, Monitor
from fleet.errors import Conflict, Unschedulable
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.sched.placement import Engine
from fleet.store import Store
from fleet.verify import violations


@dataclass(frozen=True)
class Check:
    name: str
    promise: str
    passed: bool
    detail: str = ""


def _node(name: str = "n0", cpu: int = 1000) -> Node:
    return Node(name=name, capacity=Resources(cpu=cpu, memory=cpu))


def _task(name: str, cpu: int = 100, priority: int = 100, **kw) -> Task:
    return Task(
        spec=TaskSpec(
            name=name,
            needs=Resources(cpu=cpu, memory=cpu),
            priority=priority,
            **kw,
        )
    )


def check_stale_writes_bounce() -> Check:
    store = Store()
    store.add_task(_task("t"))
    held = store.get_task("t")
    store.update_task(held, read_generation=1)
    try:
        store.update_task(held, read_generation=1)
        passed = False
    except Conflict:
        passed = True
    return Check(
        name="stale-writes-bounce",
        promise="a write carrying an old generation is refused, never merged",
        passed=passed,
    )


def check_refusals_are_sentences() -> Check:
    store = Store()
    store.add_node(_node())
    big = _task("big", cpu=9000)
    store.add_task(big)
    try:
        Scheduler().schedule(store, big)
        return Check(
            name="refusals-are-sentences",
            promise="an unschedulable task's error names every node's reason",
            passed=False,
        )
    except Unschedulable as refused:
        text = str(refused)
        return Check(
            name="refusals-are-sentences",
            promise="an unschedulable task's error names every node's reason",
            passed="n0" in text and "cpu" in text,
            detail=text,
        )


def check_placement_is_deterministic() -> Check:
    def once() -> dict[str, str]:
        store = Store()
        for number in range(3):
            store.add_node(_node(f"n{number}"))
        engine = Engine()
        for number in range(5):
            engine.submit(store, _task(f"t{number}", cpu=300))
        engine.one_pass(store, now=0)
        return {task.spec.name: task.node for task in store.active_tasks()}

    return Check(
        name="placement-is-deterministic",
        promise="the same cluster and queue place identically every time",
        passed=once() == once(),
    )


def check_silence_costs_scheduling_before_workloads() -> Check:
    store = Store()
    store.add_node(_node())
    task = _task("t")
    task.bound_to("n0")
    store.add_task(task)
    monitor = Monitor()
    monitor.sweep(store, now=5)
    early = store.get_task("t").phase == "Bound" and not store.get_node("n0").ready
    monitor.sweep(store, now=EVICT_AFTER + 1)
    late = store.get_task("t").phase == "Pending"
    return Check(
        name="silence-has-two-timers",
        promise="a silent node loses eligibility quickly and workloads slowly",
        passed=early and late,
    )


def check_budgets_hold_the_floor() -> Check:
    store = Store()
    store.add_node(_node("a"))
    store.add_node(_node("b"))
    for number, home in enumerate(["a", "a", "b"]):
        task = _task(f"w{number}", labels=(("app", "web"),))
        task.bound_to(home)
        store.add_task(task)
    guard = Guard(
        budgets=[
            Budget(
                name="floor",
                selector_key="app",
                selector_value="web",
                min_available=2,
            )
        ]
    )
    evicted, refused = guard.drain(store, "a")
    return Check(
        name="budgets-hold-the-floor",
        promise="a drain never takes availability below the stated floor",
        passed=len(evicted) == 1 and len(refused) == 1,
    )


def check_reconcile_is_idempotent() -> Check:
    store = Store()
    deployer = Deployer()
    spec = DeploySpec(
        name="web",
        replicas=3,
        template=TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100)),
    )
    deployer.reconcile(store, spec)
    writes = store.writes
    deployer.reconcile(store, spec)
    return Check(
        name="reconcile-is-idempotent",
        promise="a converged controller writes nothing",
        passed=store.writes == writes,
    )


def check_invariants_hold_after_churn() -> Check:
    store = Store()
    for number in range(3):
        store.add_node(_node(f"n{number}"))
    engine = Engine()
    for number in range(8):
        engine.submit(store, _task(f"t{number}", cpu=300, priority=number * 10))
    for now in range(6):
        engine.one_pass(store, now)
    broken = violations(store)
    return Check(
        name="invariants-hold-after-churn",
        promise="no sequence of engine passes leaves the store inconsistent",
        passed=not broken,
        detail="; ".join(broken),
    )


EVERY_CHECK = (
    check_stale_writes_bounce,
    check_refusals_are_sentences,
    check_placement_is_deterministic,
    check_silence_costs_scheduling_before_workloads,
    check_budgets_hold_the_floor,
    check_reconcile_is_idempotent,
    check_invariants_hold_after_churn,
)


@dataclass
class Conformance:
    results: list[Check] = field(default_factory=list)

    def run(self) -> list[Check]:
        from fleet.conformance2 import SECOND_WAVE
        from fleet.conformance3 import THIRD_WAVE
        from fleet.conformance4 import FOURTH_WAVE

        self.results = [
            check()
            for check in (*EVERY_CHECK, *SECOND_WAVE, *THIRD_WAVE, *FOURTH_WAVE)
        ]
        return self.results

    def failing(self) -> list[Check]:
        return [check for check in self.results if not check.passed]

    def report(self) -> str:
        if not self.results:
            self.run()
        lines = ["fleet conformance"]
        for check in self.results:
            mark = "pass" if check.passed else "FAIL"
            lines.append(f"  [{mark}] {check.name}: {check.promise}")
        failing = self.failing()
        lines.append(
            f"{len(self.results)} checks, {len(failing)} failing"
        )
        return "\n".join(lines)
