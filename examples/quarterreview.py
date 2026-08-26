"""The quarterly capacity review: three questions, three organs, one page.

Run with: python -m examples.quarterreview
"""

from __future__ import annotations

from fleet.capacityforecast import UsageLog
from fleet.energy import consolidation_savings, fleet_watts
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store
from fleet.whatifbill import price_expansion, receipt


def grown_fleet() -> Store:
    store = Store()
    for number in range(6):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    for number in range(8):
        task = Task(
            spec=TaskSpec(
                name=f"svc-{number}", needs=Resources(cpu=400, memory=400)
            )
        )
        task.bound_to(f"n{number % 4}")
        store.add_task(task)
    return store


def when_do_we_fill() -> None:
    log = UsageLog(window=90)
    base = 2000
    for week, growth in enumerate((0, 150, 290, 460, 600, 740)):
        log.record(week * 10, base + growth)
    forecast = log.forecast(capacity=6000, now=50)
    print(f"when do we fill: {forecast.line()}")


def what_would_it_cost(store: Store) -> None:
    hourly = dict.fromkeys(store.nodes, 10)
    result = price_expansion(
        store, hourly, count=2, cpu=1000, node_hourly=10
    )
    print(receipt("we add two standard nodes", result), end="")


def what_do_we_waste(store: Store) -> None:
    watts = fleet_watts(store)
    recoverable = consolidation_savings(store)
    print(
        f"what do we waste: {watts}W burning now, {recoverable}W "
        f"recoverable by packing and powering down"
    )


def main() -> int:
    store = grown_fleet()
    print("the quarter in three questions")
    when_do_we_fill()
    what_would_it_cost(store)
    what_do_we_waste(store)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
