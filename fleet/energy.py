"""Power-aware placement: watts are a resource that arrives on a schedule.

A node draws a floor of idle watts plus a slope per unit of work.
The first guess was that packing two half-loads onto one node saves a
floor; the meter says both fleets burn 400W, because the emptied node
keeps burning its floor while it is powered on. Consolidation saves
nothing until the freed node powers down, and consolidation_savings
prices exactly that power-down. The carbon calendar prices the watts
by when they are spent,
because the same joule costs triple at the evening peak. Deferrable
work shifts into the green windows and the shifter reports both
numbers, since "we moved the batch" only matters if the grams moved
with it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.objects import Node, Task, allocated
from fleet.store import Store

IDLE_WATTS = 100
WATTS_PER_CPU = 0.2


def node_watts(node: Node, active: list[Task]) -> float:
    used = allocated(node, active).cpu
    if used == 0:
        return float(IDLE_WATTS) if node.ready else 0.0
    return IDLE_WATTS + used * WATTS_PER_CPU


def fleet_watts(store: Store) -> float:
    active = store.active_tasks()
    return round(
        sum(node_watts(node, active) for node in store.nodes.values()), 1
    )


def consolidation_savings(store: Store) -> float:
    """Watts saved if every task were packed onto the fewest nodes."""
    active = store.active_tasks()
    demand = sum(task.spec.needs.cpu for task in active)
    nodes = sorted(
        (node for node in store.nodes.values() if node.ready),
        key=lambda node: -node.capacity.cpu,
    )
    packed_floors = 0
    room = 0
    for node in nodes:
        if room >= demand:
            break
        packed_floors += 1
        room += node.capacity.cpu
    packed = packed_floors * IDLE_WATTS + demand * WATTS_PER_CPU
    return round(fleet_watts(store) - packed, 1)


@dataclass(frozen=True)
class CarbonWindow:
    starts: int
    ends: int
    grams_per_watt: float


@dataclass
class CarbonCalendar:
    windows: list[CarbonWindow] = field(default_factory=list)
    default_grams: float = 1.0

    def add(self, window: CarbonWindow) -> None:
        if window.ends <= window.starts:
            raise Invalid("a carbon window must have width")
        self.windows.append(window)

    def intensity(self, tick: int) -> float:
        for window in self.windows:
            if window.starts <= tick < window.ends:
                return window.grams_per_watt
        return self.default_grams

    def greenest(self, starts: int, ends: int, span: int) -> int:
        """The start tick of the cheapest span in [starts, ends)."""
        if span <= 0 or starts + span > ends:
            raise Invalid("the span does not fit the range")
        best_start = starts
        best_cost = None
        for candidate in range(starts, ends - span + 1):
            cost = sum(
                self.intensity(tick)
                for tick in range(candidate, candidate + span)
            )
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best_start = candidate
        return best_start


@dataclass
class BatchShifter:
    calendar: CarbonCalendar
    shifted: list[str] = field(default_factory=list)

    def place(
        self, job: str, watts: float, arrival: int, deadline: int, span: int
    ) -> tuple[int, float]:
        """Returns the chosen start and the grams saved against running now."""
        naive = sum(
            self.calendar.intensity(tick) * watts
            for tick in range(arrival, arrival + span)
        )
        start = self.calendar.greenest(arrival, deadline, span)
        chosen = sum(
            self.calendar.intensity(tick) * watts
            for tick in range(start, start + span)
        )
        saved = round(naive - chosen, 1)
        self.shifted.append(
            f"{job}: [{arrival} -> {start}], {saved}g saved"
        )
        return start, saved

    def statement(self) -> str:
        return "\n".join(self.shifted) if self.shifted else "nothing shifted"
