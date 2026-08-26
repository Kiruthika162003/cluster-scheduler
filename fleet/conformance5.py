"""The fifth conformance wave: the newest organs sign their promises.

Crash backoff never exceeds its cap, priority inheritance shields
the holder from the middle band, the scheduler's measured complexity
stays inside its budget, a truthful backfill tenant is never
evicted, and a migration that cannot converge says so instead of
running forever. Same rule as always: the smallest scenario that
would catch each promise breaking.
"""

from __future__ import annotations

from fleet.backfill import Backfiller
from fleet.conformance import Check
from fleet.crashloop import BACKOFF_CAP, CrashTracker
from fleet.holds import Hold, HoldLedger
from fleet.migrations import migrate_or_explain
from fleet.objects import Node, Resources
from fleet.priorityinversion import InversionGuard
from fleet.schedbench import Bench


def check_backoff_respects_the_cap() -> Check:
    tracker = CrashTracker()
    waits = [tracker.crashed("web", now=tick * 200) for tick in range(12)]
    return Check(
        name="backoff-respects-the-cap",
        promise="the crash wait doubles but never exceeds its cap",
        passed=max(waits) == BACKOFF_CAP and waits[0] < waits[-1],
    )


def check_inheritance_shields_the_holder() -> Check:
    guard = InversionGuard()
    guard.track("critical", 1000)
    guard.track("scavenger", 0)
    guard.acquires("scavenger", "lock")
    guard.blocks_on("critical", "lock")
    guard.inherit(now=0)
    shielded = not guard.preemptable_by("scavenger", 100)
    guard.releases("scavenger", now=1)
    returned = guard.priorities["scavenger"] == 0
    return Check(
        name="inheritance-shields-the-holder",
        promise="the lock holder borrows rank and returns it on release",
        passed=shielded and returned,
    )


def check_complexity_stays_budgeted() -> Check:
    bench = Bench()
    bench.ladder([(5, 10), (10, 20), (20, 40)])
    passed, _ = bench.regression_gate(budget_exponent=1.0)
    return Check(
        name="complexity-stays-budgeted",
        promise="scheduling work grows with nodes times tasks, no faster",
        passed=passed,
    )


def check_truthful_tenants_never_evicted() -> Check:
    ledger = HoldLedger()
    node = Node(name="n0", capacity=Resources(cpu=1000, memory=1000))
    ledger.book(
        Hold(
            name="h",
            node="n0",
            amount=Resources(cpu=500, memory=500),
            starts=20,
            ends=40,
        ),
        node,
    )
    filler = Backfiller(ledger=ledger)
    loan = filler.borrow("honest", cpu=400, needs_ticks=20, node="n0", now=0)
    filler.finish("honest", now=20)
    swept = filler.sweep(now=20)
    return Check(
        name="truthful-tenants-never-evicted",
        promise="a job admitted to finish before the window is never swept",
        passed=loan is not None and swept == [] and filler.evictions == 0,
    )


def check_divergence_is_named() -> Check:
    migration = migrate_or_explain(
        memory=1000, dirty_rate=500, copy_rate=100, pause_budget=1
    )
    return Check(
        name="divergence-is-named",
        promise="a migration that cannot converge says so and stops",
        passed="will never converge" in migration.verdict
        and len(migration.rounds) == 1,
    )


FIFTH_WAVE = (
    check_backoff_respects_the_cap,
    check_inheritance_shields_the_holder,
    check_complexity_stays_budgeted,
    check_truthful_tenants_never_evicted,
    check_divergence_is_named,
)
