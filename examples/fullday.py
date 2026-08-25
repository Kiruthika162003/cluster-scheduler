"""One full day: morning apply, noon incident, evening batch, night handoff.

Run with: python -m examples.fullday
"""

from __future__ import annotations

from fleet.api import Fleet
from fleet.catalog import Catalog, CatalogEntry
from fleet.control.dagjobs import DagRun
from fleet.control.finalizers import Departures
from fleet.cordonttl import CordonLeases
from fleet.depends import DependencyGraph
from fleet.handoff import handoff
from fleet.manifest import gates_from, parse
from fleet.notes import Noteboard
from fleet.objects import Node, Resources
from fleet.sched.queue import SchedulingQueue


def morning(fleet: Fleet) -> None:
    manifest = parse(
        {
            "deploys": [
                {"name": "web", "replicas": 4, "cpu": 300,
                 "labels": {"app": "web"}},
                {"name": "api", "replicas": 2, "cpu": 400,
                 "labels": {"app": "api"}},
            ],
            "budgets": [
                {"name": "web-floor", "selector_key": "app",
                 "selector_value": "web", "min_available": 3},
            ],
        }
    )
    _, fleet.guard = gates_from(manifest)
    for spec in manifest.deploys:
        fleet.apply_deploy("morning", spec)
    for _ in range(3):
        fleet.step()
    for task in fleet.store.tasks.values():
        if task.phase == "Bound":
            task.phase = "Running"
    print(f"morning: {len(fleet.store.tasks)} tasks running across "
          f"{len(fleet.store.nodes)} nodes")


def noon(fleet: Fleet, catalog: Catalog) -> None:
    victim = fleet.store.get_task("web-0").node
    moved = fleet.retire_node("noon-oncall", victim)
    for _ in range(3):
        fleet.step()
    for task in fleet.store.tasks.values():
        if task.phase == "Bound":
            task.phase = "Running"
    owner = catalog.owner_of("web")
    print(f"noon: {victim} retired, {moved} tasks moved, "
          f"paging {catalog.page_target('web', 0)} of {owner.team}")


def evening() -> DagRun:
    graph = DependencyGraph()
    graph.declare("transform", "extract")
    graph.declare("load", "transform")
    run = DagRun(graph=graph)
    for _ in range(5):
        for job in run.launch_ready():
            run.finish(job, "succeeded")
        if run.state() != "running":
            break
    print(f"evening: batch pipeline {run.state()}, "
          f"order {', '.join(run.launched)}")
    return run


def night(fleet: Fleet) -> None:
    leases = CordonLeases()
    notes = Noteboard()
    notes.pin(
        "web", "noon-oncall", "one node retired at noon, capacity is tighter",
        now=80,
    )
    page = handoff(
        90,
        leases,
        notes,
        Departures(),
        SchedulingQueue(),
        fleet.journal,
    )
    print()
    print(page)


def main() -> int:
    fleet = Fleet()
    for number in range(4):
        fleet.store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    catalog = Catalog()
    catalog.register(
        CatalogEntry(
            deploy="web",
            team="storefront",
            channel="#storefront",
            escalation=("meera", "raj"),
        )
    )
    morning(fleet)
    noon(fleet, catalog)
    evening()
    night(fleet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
