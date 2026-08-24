"""Upgrading four nodes: the budget sets the dip, one spare erases it.

Eight replicas on four full nodes, budget floor of six. The plain walk
cordons each node in turn and its drained pair has nowhere to go until
the patched node returns: the serving floor across the campaign is 6,
exactly the budget, which is what the budget is for. Add one surge node
for the duration and every drained pair lands immediately: the floor is
8, the campaign never dips at all, and the surge node leaves empty when
the walk ends. The first version of the walk cordoned by marking nodes
unready and measured a floor of 6 even with the surge, because a
cordoned node is not a dead node and the meter needed to know the
difference.
"""

from __future__ import annotations

from fleet.control.budget import Budget, Guard
from fleet.control.deploy import DeploySpec
from fleet.objects import Resources, TaskSpec
from fleet.sim.cluster import Sim
from fleet.trials.verdict import Verdict
from fleet.upgradewalk import Walk


def _setup() -> Sim:
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
    return sim


def _walk(surge: Resources | None) -> tuple[int, int, list[str]]:
    sim = _setup()
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
    walk.upgrade(sim, ["n0", "n1", "n2", "n3"], surge=surge)
    return walk.floor_seen, sim.serving_count(), sorted(sim.store.nodes)


def run() -> Verdict:
    plain_floor, plain_final, plain_nodes = _walk(None)
    surge_floor, surge_final, surge_nodes = _walk(Resources(cpu=1000, memory=1000))

    numbers = {
        "plain_floor": plain_floor,
        "surge_floor": surge_floor,
        "final_serving_either": plain_final,
        "surge_node_removed": "surge" not in surge_nodes,
    }
    holds = (
        plain_floor == 6
        and surge_floor == 8
        and plain_final == surge_final == 8
        and "surge" not in surge_nodes
        and plain_nodes == ["n0", "n1", "n2", "n3"]
    )
    return Verdict(
        trial="kernelwalk",
        sentence=(
            "the plain upgrade walk dips to the budget floor of 6 while "
            "each drained pair waits for its node to return; one surge "
            "machine holds the floor at 8 for the whole campaign and "
            "leaves empty when the walk ends"
        ),
        numbers=numbers,
        holds=holds,
    )
