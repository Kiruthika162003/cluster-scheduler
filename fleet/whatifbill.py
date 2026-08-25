"""What-if pricing: the capacity question and the invoice, answered together.

Adding nodes buys headroom and costs rent; the two numbers belong on
one line. The bill planner runs the what-if twin, prices both worlds
with the same hourly table, and reports headroom per currency-unit so
two different expansion options can be compared by the only ratio
that matters. The twin never touches the live store, and the rendered
receipt carries before, after, and the price of the difference.
"""

from __future__ import annotations

import io

from fleet.costreport import split_bill
from fleet.objects import Node, Resources
from fleet.snapshot import dump, restore
from fleet.store import Store
from fleet.whatif import _headroom


def price_expansion(
    store: Store,
    hourly: dict[str, int],
    count: int,
    cpu: int,
    node_hourly: int,
    hours: int = 720,
) -> dict:
    twin = restore(dump(store))
    twin_hourly = dict(hourly)
    for number in range(count):
        name = f"whatif-{number}"
        twin.nodes[name] = Node(
            name=name, capacity=Resources(cpu=cpu, memory=cpu)
        )
        twin_hourly[name] = node_hourly

    lines_before, idle_before = split_bill(store, hourly, hours)
    lines_after, idle_after = split_bill(twin, twin_hourly, hours)
    bill_before = sum(line.charge for line in lines_before) + idle_before
    bill_after = sum(line.charge for line in lines_after) + idle_after
    added_rent = count * node_hourly * hours

    headroom_before = _headroom(store)
    headroom_after = _headroom(twin)
    gained = headroom_after - headroom_before

    return {
        "bill_before": round(bill_before, 2),
        "bill_after": round(bill_after, 2),
        "added_rent_if_occupied": added_rent,
        "headroom_before": headroom_before,
        "headroom_after": headroom_after,
        "headroom_per_hourly_unit": (
            round(gained / (count * node_hourly), 1)
            if count and node_hourly
            else 0.0
        ),
    }


def receipt(question: str, result: dict) -> str:
    out = io.StringIO()
    out.write(f"what if {question}\n")
    out.write(
        f"  headroom: {result['headroom_before']}m -> "
        f"{result['headroom_after']}m\n"
    )
    out.write(
        f"  the month's bill: {result['bill_before']} -> "
        f"{result['bill_after']} once occupied, "
        f"up to {result['added_rent_if_occupied']} more\n"
    )
    out.write(
        f"  headroom per hourly unit: {result['headroom_per_hourly_unit']}\n"
    )
    return out.getvalue()
