"""The eighth conformance wave: the last organs take the oath.

Small jobs spare the eight-box, interesting traces are never
sampled away, the marginal replica goes where arithmetic says, the
delivery ledger refuses double failures, the queueing knee doubles
where the formula says, and the lame duck refuses work before the
drain begins.
"""

from __future__ import annotations

from fleet.changefail import DeliveryLedger
from fleet.conformance import Check
from fleet.gracefulshutdown import Shutdown
from fleet.queuemodel import predict
from fleet.redundancymath import Tier, best_marginal_replica
from fleet.sched.devices import DeviceNode, DevicePool
from fleet.tailsampling import TailSampler, Trace


def check_the_eight_box_stays_whole() -> Check:
    pool = DevicePool()
    pool.add_node(DeviceNode(name="big8", slots=8))
    pool.add_node(DeviceNode(name="tiny2", slots=2))
    chosen = pool.place("small", count=2)
    return Check(
        name="the-eight-box-stays-whole",
        promise="a two-slot job never parks on an empty eight-slot box",
        passed=chosen == "tiny2",
    )


def check_interesting_traces_survive_sampling() -> Check:
    sampler = TailSampler(slow_line=100, keep_one_in=1000)
    for number in range(500):
        sampler.offer(Trace(name=f"ok-{number}", latency=5, failed=False))
    sampler.offer(Trace(name="err", latency=5, failed=True))
    sampler.offer(Trace(name="slow", latency=900, failed=False))
    return Check(
        name="interesting-traces-survive-sampling",
        promise="errors and slow traces are kept at weight one, always",
        passed=sampler.exact_interesting() == 2,
    )


def check_the_marginal_replica_follows_arithmetic() -> Check:
    tiers = [
        Tier(name="strong", single=0.999, count=2),
        Tier(name="weak", single=0.99, count=1),
    ]
    name, gain = best_marginal_replica(tiers)
    return Check(
        name="the-marginal-replica-follows-arithmetic",
        promise="the next replica lands on the weakest composed tier",
        passed=name == "weak" and gain > 0,
    )


def check_one_failure_per_deploy() -> Check:
    ledger = DeliveryLedger()
    ledger.shipped("d0", committed=0, shipped=5)
    ledger.failed("d0", noticed=6, restored=9)
    try:
        ledger.failed("d0", noticed=10, restored=12)
        doubled = True
    except Exception:
        doubled = False
    return Check(
        name="one-failure-per-deploy",
        promise="the ledger refuses a second failure on one deploy",
        passed=not doubled and ledger.failure_rate() == 1.0,
    )


def check_the_knee_doubles() -> Check:
    half = predict(arrival_rate=0.25, service_ticks=2).predicted_wait
    threequarters = predict(arrival_rate=0.375, service_ticks=2).predicted_wait
    return Check(
        name="the-knee-doubles",
        promise="wait doubles from half to three-quarters utilisation",
        passed=half == 2.0 and threequarters == 6.0,
    )


def check_the_duck_refuses_before_the_drain() -> Check:
    shutdown = Shutdown(drain_deadline=20)
    shutdown.begin(now=0)
    accepted = shutdown.accept("late", now=1, takes=1)
    return Check(
        name="the-duck-refuses-before-the-drain",
        promise="no new work lands once the lame duck act begins",
        passed=not accepted and shutdown.refused == 1,
    )


EIGHTH_WAVE = (
    check_the_eight_box_stays_whole,
    check_interesting_traces_survive_sampling,
    check_the_marginal_replica_follows_arithmetic,
    check_one_failure_per_deploy,
    check_the_knee_doubles,
    check_the_duck_refuses_before_the_drain,
)
