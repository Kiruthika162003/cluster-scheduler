"""Filter order is free money: put the cheap refusals first, measured.

The scheduler runs its filters in a fixed order and stops at the first
refusal. On a cluster where most nodes are cordoned for an upgrade
wave, asking is-ready first answers most refusals in one check, while
asking fits first does the resource arithmetic on nodes that were never
candidates. Same verdicts on every node, same placements, different
work: the counters show 108 checks against 288, which is why
real schedulers order predicates by cost and hit rate rather than by
the order someone wrote them in.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.sched import filters as flt
from fleet.sched.core import Scheduler
from fleet.store import Store
from fleet.trials.verdict import Verdict


@dataclass
class Counted:
    calls: dict[str, int] = field(default_factory=dict)

    def wrap(self, check):
        name = check.__name__

        def counted(task, node, active):
            self.calls[name] = self.calls.get(name, 0) + 1
            return check(task, node, active)

        counted.__name__ = name
        return counted

    def total(self) -> int:
        return sum(self.calls.values())


def _cluster() -> Store:
    store = Store()
    for number in range(10):
        node = Node(
            name=f"n{number}", capacity=Resources(cpu=1000, memory=1000)
        )
        if number >= 2:
            node.schedulable = False
        store.add_node(node)
    return store


def _run(order: tuple) -> tuple[int, dict[str, int], set[str]]:
    store = _cluster()
    meter = Counted()
    scheduler = Scheduler(filters=tuple(meter.wrap(check) for check in order))
    for number in range(6):
        store.add_task(
            Task(
                spec=TaskSpec(
                    name=f"t{number}", needs=Resources(cpu=300, memory=300)
                )
            )
        )
    scheduler.schedule_pending(store)
    homes = {task.node for task in store.active_tasks()}
    return meter.total(), meter.calls, homes


CHEAP_FIRST = (
    flt.is_ready,
    flt.selector_matches,
    flt.tolerates_taints,
    flt.repelled_by_peers,
    flt.fits,
)
DEAR_FIRST = (
    flt.fits,
    flt.repelled_by_peers,
    flt.tolerates_taints,
    flt.selector_matches,
    flt.is_ready,
)


def run() -> Verdict:
    cheap_total, cheap_calls, cheap_homes = _run(CHEAP_FIRST)
    dear_total, dear_calls, dear_homes = _run(DEAR_FIRST)

    numbers = {
        "checks_cheap_first": cheap_total,
        "checks_dear_first": dear_total,
        "fits_calls_cheap_first": cheap_calls.get("fits", 0),
        "fits_calls_dear_first": dear_calls.get("fits", 0),
        "same_placements": cheap_homes == dear_homes,
    }
    holds = (
        cheap_homes == dear_homes
        and cheap_total * 2 < dear_total
        and cheap_calls.get("fits", 0) == 12
        and dear_calls.get("fits", 0) == 60
    )
    return Verdict(
        trial="filterorder",
        sentence=(
            "with eight of ten nodes cordoned the cheap-first order runs "
            "the resource arithmetic 12 times and the dear-first order 60, "
            "for identical placements: predicate order is free money paid "
            "in checks nobody needed"
        ),
        numbers=numbers,
        holds=holds,
    )
