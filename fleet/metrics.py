"""Counters and gauges with a registry, rendered as one text page.

Every component keeps its own numbers; the registry is the place they
agree to be read from. Counters only go up, gauges go wherever the
truth is, and both carry their name and help line because a number
without a sentence is a guess waiting to happen. The render is stable:
sorted names, one metric per line, diffable across ticks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass
class Counter:
    name: str
    help_line: str
    value: int = 0

    def bump(self, by: int = 1) -> None:
        if by < 0:
            raise Invalid(f"counter {self.name} cannot go down")
        self.value += by


@dataclass
class Gauge:
    name: str
    help_line: str
    value: float = 0.0

    def set(self, value: float) -> None:
        self.value = value


@dataclass
class Registry:
    counters: dict[str, Counter] = field(default_factory=dict)
    gauges: dict[str, Gauge] = field(default_factory=dict)

    def counter(self, name: str, help_line: str) -> Counter:
        if name in self.gauges:
            raise Invalid(f"{name} is already a gauge")
        if name not in self.counters:
            self.counters[name] = Counter(name=name, help_line=help_line)
        return self.counters[name]

    def gauge(self, name: str, help_line: str) -> Gauge:
        if name in self.counters:
            raise Invalid(f"{name} is already a counter")
        if name not in self.gauges:
            self.gauges[name] = Gauge(name=name, help_line=help_line)
        return self.gauges[name]

    def render(self) -> str:
        lines = []
        for name in sorted(set(self.counters) | set(self.gauges)):
            if name in self.counters:
                held = self.counters[name]
                lines.append(f"# {held.help_line}")
                lines.append(f"{name} {held.value}")
            else:
                held = self.gauges[name]
                lines.append(f"# {held.help_line}")
                shown = int(held.value) if held.value == int(held.value) else held.value
                lines.append(f"{name} {shown}")
        return "\n".join(lines)


def scrape(sim) -> Registry:
    """The simulation's numbers gathered into one registry."""
    registry = Registry()
    registry.counter("scheduler_placed_total", "tasks bound by the scheduler").bump(
        sim.scheduler.placed
    )
    registry.counter("scheduler_rejected_total", "tasks refused by every node").bump(
        sim.scheduler.rejected
    )
    registry.counter("monitor_evictions_total", "tasks evicted off silent nodes").bump(
        sim.monitor.evicted
    )
    registry.counter("keeper_restarts_total", "probe failures restarted").bump(
        sim.keeper.restarts
    )
    registry.gauge("tasks_running", "tasks in phase Running").set(sim.running_count())
    registry.gauge("tasks_serving", "running tasks on ready nodes").set(
        sim.serving_count()
    )
    registry.gauge("nodes_total", "nodes in the store").set(len(sim.store.nodes))
    return registry
