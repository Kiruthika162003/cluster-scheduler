"""The storefront platform: a manifest, an upgrade, a bad night, one brief.

Run with: python -m examples.storefront
"""

from __future__ import annotations

from fleet.api import Fleet
from fleet.deploystatus import status_of
from fleet.loadbalance import Balancer, Endpoint
from fleet.manifest import gates_from, parse
from fleet.objects import Node, Resources
from fleet.oncall import brief
from fleet.roll.history import History
from fleet.roll.rolling import Roller


def main() -> int:
    manifest = parse(
        {
            "deploys": [
                {"name": "shop", "replicas": 4, "cpu": 200,
                 "labels": {"app": "shop"}},
            ],
            "quotas": [{"namespace": "default", "max_tasks": 20}],
            "budgets": [
                {"name": "shop-floor", "selector_key": "app",
                 "selector_value": "shop", "min_available": 3},
            ],
        }
    )
    fleet = Fleet()
    _, fleet.guard = gates_from(manifest)
    for number in range(4):
        fleet.store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    for spec in manifest.deploys:
        fleet.apply_deploy("platform", spec)
    for _ in range(3):
        fleet.step()
    for task in fleet.store.tasks.values():
        if task.phase == "Bound":
            task.phase = "Running"
    print(f"applied: {len(fleet.store.tasks)} shop replicas running")

    history = History(name="shop")
    history.record(manifest.deploys[0].template, note="v1")
    history.record(manifest.deploys[0].template, note="v2")
    roller = Roller()
    roll = history.rollout(replicas=4, max_surge=1)
    for _ in range(20):
        what = roller.step(fleet.store, roll)
        for task in fleet.store.pending_tasks():
            fleet.engine.queue.offer(task.spec.name, task.spec.priority)
        fleet.step()
        for task in fleet.store.tasks.values():
            if task.phase == "Bound":
                task.phase = "Running"
        if what == "done":
            break
    told = status_of(fleet.store, roller, roll)
    print(f"upgrade: {told.sentence()}")

    balancer = Balancer(
        policy="two-choices",
        endpoints=[
            Endpoint(name=name, service_ticks=1)
            for name in sorted(fleet.store.tasks)
        ],
    )
    for now in range(1, 101):
        balancer.tick(now, arrivals=3)
    print(f"traffic: worst queue depth {balancer.worst_depth} across the fleet")

    evicted, refused = fleet.drain("oncall", "n0")
    print(f"drain n0: evicted {evicted or 'nobody'}, refused {refused or 'nobody'}")
    for _ in range(2):
        fleet.step()
    page = brief(
        fleet.store,
        fleet.journal,
        since=0,
        running=fleet.store.tasks and sum(
            1 for t in fleet.store.tasks.values() if t.phase == "Running"
        ),
        serving=sum(
            1
            for t in fleet.store.tasks.values()
            if t.phase == "Running"
            and t.node
            and fleet.store.nodes[t.node].ready
        ),
    )
    print()
    print(page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
