"""A storm drill: the resilience quartet takes one outage together.

Run with: python -m examples.stormdrill
"""

from __future__ import annotations

from fleet.bulkhead import Ship
from fleet.circuitbreaker import Breaker
from fleet.hedging import Hedger
from fleet.retrybudget import RetryBudget

OUTAGE = range(20, 50)


def db_answers(tick: int) -> bool:
    return tick not in OUTAGE


def storm() -> tuple[Breaker, RetryBudget, int]:
    breaker = Breaker(name="db")
    budget = RetryBudget(ratio=0.1)
    naive_backend_calls = 0
    guarded_backend_calls = 0
    for tick in range(80):
        naive_backend_calls += 1 if db_answers(tick) else 3
        budget.send()
        allowed, _ = breaker.allow(tick)
        if not allowed:
            continue
        guarded_backend_calls += 1
        if db_answers(tick):
            breaker.succeeded(tick)
            budget.succeeded(tick)
        else:
            breaker.failed(tick)
            if budget.may_retry(tick):
                guarded_backend_calls += 1
                breaker.call(tick, works=db_answers(tick))
    return breaker, budget, naive_backend_calls - guarded_backend_calls


def compartments() -> Ship:
    ship = Ship()
    ship.partition("db", pool_size=2, queue_size=1)
    ship.partition("cache", pool_size=4, queue_size=2)
    for number in range(6):
        ship.submit("db", f"stuck-{number}", now=0, takes=1000)
    for number in range(3):
        ship.submit("cache", f"hit-{number}", now=0, takes=1)
    return ship


def tail_purchase() -> Hedger:
    hedger = Hedger(hedge_delay=50)
    for _ in range(95):
        hedger.call(primary_latency=10, backup_latency=12)
    for _ in range(5):
        hedger.call(primary_latency=300, backup_latency=12)
    return hedger


def main() -> int:
    breaker, budget, spared = storm()
    print("the storm, guarded:")
    print(f"  breaker: {breaker.state}, saved {breaker.saved()} waits")
    print(f"  retries: {budget.statement()}")
    print(f"  backend spared {spared} calls against the naive client")
    ship = compartments()
    print(ship.report())
    hedger = tail_purchase()
    print(f"  hedging: {hedger.trade()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
