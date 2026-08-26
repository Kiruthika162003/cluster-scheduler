"""The seventh conformance wave: the truth-telling organs sign last.

The watermark never retreats, a saga unwinds in reverse order, the
robust detector sees the spike the z-score hides, the seasonal
judge separates 3am from noon, the closed-loop flattery is at
least an order of magnitude, and the domain audit catches the
stacked deploy that every health check passes.
"""

from __future__ import annotations

from fleet.conformance import Check
from fleet.failuredomains import DomainAudit
from fleet.loadgen import omission_gap
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.outliers import robust_outliers, zscore_outliers
from fleet.sagas import Saga, Step
from fleet.seasonal import HOURS_PER_WEEK, SeasonalBaseline
from fleet.store import Store
from fleet.watermarks import WatermarkStream


def check_watermarks_never_retreat() -> Check:
    stream = WatermarkStream(window_size=10, allowance=3)
    stream.accept(20, value=1)
    high = stream.watermark
    stream.accept(18, value=1)
    return Check(
        name="watermarks-never-retreat",
        promise="an out-of-order event never moves the watermark backwards",
        passed=stream.watermark == high,
    )


def check_sagas_unwind_in_reverse() -> Check:
    order: list[str] = []
    steps = [
        Step("first", lambda: order.append("do-1") or True,
             lambda: order.append("undo-1")),
        Step("second", lambda: order.append("do-2") or True,
             lambda: order.append("undo-2")),
        Step("boom", lambda: False, lambda: None),
    ]
    Saga(name="drill", steps=steps).run()
    return Check(
        name="sagas-unwind-in-reverse",
        promise="compensations run opposite to the order effects were made",
        passed=order == ["do-1", "do-2", "undo-2", "undo-1"],
    )


def check_the_spike_cannot_hide() -> Check:
    fleet = {f"n{number}": 10.0 + (number % 3) for number in range(9)}
    fleet["sick"] = 400.0
    robust = [outlier.name for outlier in robust_outliers(fleet)]
    naive = zscore_outliers(fleet)
    return Check(
        name="the-spike-cannot-hide",
        promise="the robust detector flags what the z-score misses",
        passed=robust == ["sick"] and naive == [],
    )


def check_three_am_is_not_noon() -> Check:
    baseline = SeasonalBaseline()
    for week in range(6):
        for hour in range(HOURS_PER_WEEK):
            value = 100.0 if hour % 24 < 6 else 1000.0
            baseline.learn(week * HOURS_PER_WEEK + hour, value)
    night = baseline.judge(3, 102.0)
    noon = baseline.judge(12, 102.0)
    return Check(
        name="three-am-is-not-noon",
        promise="the same reading is normal at night and a hole at noon",
        passed=night == "normal for this hour" and noon.startswith("hole"),
    )


def check_the_closed_loop_flatters() -> Check:
    gap = omission_gap(
        service_ticks=2, stall=(100, 160), duration=300, every=4
    )
    return Check(
        name="the-closed-loop-flatters",
        promise="coordinated omission hides at least tenfold latency",
        passed=gap["flattery_factor"] >= 10.0,
    )


def check_stacked_deploys_are_caught() -> Check:
    store = Store()
    for name, rack in (("n0", "r1"), ("n1", "r1"), ("n2", "r2")):
        store.add_node(
            Node(
                name=name,
                capacity=Resources(cpu=1000, memory=1000),
                labels={"rack": rack, "zone": "za"},
            )
        )
    for replica, node in enumerate(("n0", "n1", "n0")):
        task = Task(
            spec=TaskSpec(
                name=f"web-{replica}", needs=Resources(cpu=100, memory=100)
            )
        )
        task.bound_to(node)
        store.add_task(task)
    audit = DomainAudit(store=store, levels=("rack",), floors={"web": 1})
    return Check(
        name="stacked-deploys-are-caught",
        promise="a healthy-looking deploy stacked on one rack fails the audit",
        passed=len(audit.verdicts()) == 1,
    )


SEVENTH_WAVE = (
    check_watermarks_never_retreat,
    check_sagas_unwind_in_reverse,
    check_the_spike_cannot_hide,
    check_three_am_is_not_noon,
    check_the_closed_loop_flatters,
    check_stacked_deploys_are_caught,
)
