"""The monthly page: capacity, the bill, the movers, one screen for the owner.

Run with: python -m examples.execmonthly
"""

from __future__ import annotations

from fleet.costanomaly import anomalies, attribution
from fleet.costreport import rendered as bill_page
from fleet.fleetsummary import summary
from fleet.metering import Meter
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def build_month() -> tuple[Store, Meter, Meter, dict[str, int]]:
    store = Store()
    hourly = {}
    for number in range(4):
        name = f"n{number}"
        store.add_node(
            Node(name=name, capacity=Resources(cpu=2000, memory=2000))
        )
        hourly[name] = 12
    workloads = (
        ("search-api", "search", 900, "n0"),
        ("search-index", "search", 700, "n1"),
        ("ads-bidder", "ads", 500, "n2"),
        ("ml-train", "ml", 1200, "n3"),
    )
    for name, space, cpu, home in workloads:
        task = Task(
            spec=TaskSpec(
                name=name, needs=Resources(cpu=cpu, memory=cpu), namespace=space
            )
        )
        task.bound_to(home)
        task.phase = "Running"
        store.add_task(task)
    last_month = Meter()
    last_month.cpu_ticks = {"search": 40000, "ads": 30000, "ml": 8000}
    this_month = Meter()
    for _ in range(30):
        this_month.sample(store)
    return store, last_month, this_month, hourly


def main() -> int:
    store, last_month, this_month, hourly = build_month()
    print(summary(store, usage={}, cpu_growth=0.01, memory_growth=0.02))
    print(bill_page(store, hourly, hours=720))
    print("month over month:")
    for finding in anomalies(last_month, this_month):
        print(f"  {finding}")
    print()
    print(attribution(last_month, this_month))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
