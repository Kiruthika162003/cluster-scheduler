"""Scenarios: drills written as data, expectations checked as they pass.

A scenario is a list of cues, each a tick, a verb and its arguments,
plus expectations pinned to ticks: at tick 40 serving should be 8. The
player walks a Sim through the script, fires cues on their ticks,
checks expectations on theirs, and reports every miss with both
numbers. Drills stop being prose in a wiki and become files that fail,
which is the only kind of drill that stays true.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.control.deploy import DeploySpec
from fleet.errors import Invalid
from fleet.objects import Node, Resources, TaskSpec
from fleet.sim.cluster import Sim


@dataclass(frozen=True)
class Cue:
    tick: int
    verb: str
    args: tuple

    def __post_init__(self) -> None:
        if self.verb not in PLAYS:
            raise Invalid(f"unknown verb {self.verb}")


@dataclass(frozen=True)
class Expectation:
    tick: int
    meter: str
    value: int

    def __post_init__(self) -> None:
        if self.meter not in METERS:
            raise Invalid(f"unknown meter {self.meter}")


def _play_scale(sim: Sim, name: str, replicas: int) -> None:
    for at, spec in enumerate(sim.deploys):
        if spec.name == name:
            sim.deploys[at] = DeploySpec(
                name=name, replicas=replicas, template=spec.template
            )
            return
    sim.deploys.append(
        DeploySpec(
            name=name,
            replicas=replicas,
            template=TaskSpec(name="tpl", needs=Resources(cpu=300, memory=300)),
        )
    )


def _play_kill_node(sim: Sim, node_name: str) -> None:
    node = sim.store.get_node(node_name)
    node.ready = False
    sim.script.silences[node_name] = (sim.now, 10**9)


def _play_heal_node(sim: Sim, node_name: str) -> None:
    sim.script.silences.pop(node_name, None)
    sim.monitor.beat(sim.store, node_name, sim.now)


def _play_add_node(sim: Sim, node_name: str, cpu: int) -> None:
    sim.store.add_node(
        Node(name=node_name, capacity=Resources(cpu=cpu, memory=cpu))
    )
    sim.monitor.beat(sim.store, node_name, sim.now)


PLAYS = {
    "scale": _play_scale,
    "kill-node": _play_kill_node,
    "heal-node": _play_heal_node,
    "add-node": _play_add_node,
}

METERS = {
    "running": lambda sim: sim.running_count(),
    "serving": lambda sim: sim.serving_count(),
    "nodes": lambda sim: len(sim.store.nodes),
    "evictions": lambda sim: sim.monitor.evicted,
}


@dataclass
class Player:
    cues: list[Cue] = field(default_factory=list)
    expectations: list[Expectation] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)

    def run(self, sim: Sim, ticks: int) -> bool:
        for now in range(ticks):
            for cue in self.cues:
                if cue.tick == now:
                    PLAYS[cue.verb](sim, *cue.args)
            sim.tick()
            for expectation in self.expectations:
                if expectation.tick != now:
                    continue
                seen = METERS[expectation.meter](sim)
                if seen != expectation.value:
                    self.misses.append(
                        f"[{now}] {expectation.meter}: expected "
                        f"{expectation.value}, saw {seen}"
                    )
        return not self.misses
