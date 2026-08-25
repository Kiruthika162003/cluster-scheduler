"""Patch Tuesday: the calendar holds the walk until the freeze lifts.

Run with: python -m examples.patchtuesday
"""

from __future__ import annotations

from fleet.control.budget import Budget, Guard
from fleet.control.deploy import DeploySpec
from fleet.maintenance import Calendar, Window
from fleet.objects import Resources, TaskSpec
from fleet.sim.cluster import Sim
from fleet.upgradewalk import Walk


def main() -> int:
    calendar = Calendar()
    calendar.add(Window(start=0, end=30, reason="launch freeze"))

    sim = Sim()
    sim.add_nodes(4)
    sim.deploys.append(
        DeploySpec(
            name="web",
            replicas=8,
            template=TaskSpec(
                name="tpl",
                needs=Resources(cpu=400, memory=400),
                labels=(("app", "web"),),
            ),
        )
    )
    sim.run(5)

    guard = Guard(
        budgets=[
            Budget(
                name="floor",
                selector_key="app",
                selector_value="web",
                min_available=6,
            )
        ]
    )
    walk = Walk(guard=guard)

    for attempt_tick in (10, 30):
        allowed, opens = calendar.may_change(attempt_tick)
        if not allowed:
            print(
                f"tick {attempt_tick}: walk refused by the calendar, "
                f"opens at {opens}"
            )
            continue
        print(f"tick {attempt_tick}: calendar clear, walking the fleet")
        walk.upgrade(
            sim, ["n0", "n1", "n2", "n3"], surge=Resources(cpu=1000, memory=1000)
        )
    print(
        f"patched {len(walk.patched)} nodes, serving floor {walk.floor_seen}, "
        f"refusals recorded {calendar.refusals}"
    )
    print(f"final serving: {sim.serving_count()} of 8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
