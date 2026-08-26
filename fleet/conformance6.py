"""The sixth conformance wave: the client-side organs sign too.

An open breaker refuses fast, a bankrupt retry budget denies, a
full compartment never touches its neighbours, a hedge fires only
past its delay, a stampede costs one trip, and consistent hashing
moves a slice rather than the furniture. The smallest scenario for
each, as always.
"""

from __future__ import annotations

from fleet.bulkhead import Ship
from fleet.circuitbreaker import FAILURE_THRESHOLD, Breaker
from fleet.conformance import Check
from fleet.hedging import Hedger
from fleet.retrybudget import RetryBudget
from fleet.shardmap import Ring, moved_keys
from fleet.singleflight import SingleFlight


def check_open_breakers_refuse_fast() -> Check:
    breaker = Breaker(name="db")
    for count in range(FAILURE_THRESHOLD):
        breaker.call(count, works=False)
    outcome = breaker.call(FAILURE_THRESHOLD, works=True)
    return Check(
        name="open-breakers-refuse-fast",
        promise="an open breaker answers immediately with its name",
        passed=outcome == "refused: breaker db is open",
    )


def check_bankrupt_budgets_deny() -> Check:
    budget = RetryBudget(ratio=0.1)
    granted = budget.may_retry(0)
    return Check(
        name="bankrupt-budgets-deny",
        promise="no successes earned means no retries granted",
        passed=not granted and budget.denied == 1,
    )


def check_compartments_hold() -> Check:
    ship = Ship()
    ship.partition("db", pool_size=1, queue_size=0)
    ship.partition("cache", pool_size=1, queue_size=0)
    ship.submit("db", "stuck", now=0, takes=1000)
    refused = ship.submit("db", "next", now=0, takes=1)
    neighbour = ship.submit("cache", "fine", now=0, takes=1)
    return Check(
        name="compartments-hold",
        promise="a full compartment refuses without touching its neighbour",
        passed=refused.startswith("refused") and neighbour == "running",
    )


def check_hedges_wait_their_delay() -> Check:
    hedger = Hedger(hedge_delay=50)
    fast = hedger.call(primary_latency=10, backup_latency=10)
    slow = hedger.call(primary_latency=200, backup_latency=10)
    return Check(
        name="hedges-wait-their-delay",
        promise="a backup fires only when the primary outlives the delay",
        passed=not fast.hedged and slow.hedged and slow.delivered == 60,
    )


def check_stampedes_cost_one_trip() -> Check:
    group = SingleFlight()
    group.ask("leader", "hot")
    for number in range(9):
        group.ask(f"follower-{number}", "hot")
    return Check(
        name="stampedes-cost-one-trip",
        promise="ten identical questions in flight make one backend trip",
        passed=group.trips_flown == 1 and group.trips_saved == 9,
    )


def check_the_ring_moves_a_slice() -> Check:
    keys = [f"key-{number}" for number in range(500)]
    ring = Ring()
    for number in range(5):
        ring.add(f"n{number}")
    before = ring.assignment(keys)
    ring.add("n5")
    _, share = moved_keys(before, ring.assignment(keys))
    return Check(
        name="the-ring-moves-a-slice",
        promise="a sixth node relocates well under half the keys",
        passed=0.0 < share < 0.5,
    )


SIXTH_WAVE = (
    check_open_breakers_refuse_fast,
    check_bankrupt_budgets_deny,
    check_compartments_hold,
    check_hedges_wait_their_delay,
    check_stampedes_cost_one_trip,
    check_the_ring_moves_a_slice,
)
