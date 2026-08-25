"""A NOC week: probes watch, budgets burn, pages route, toil gets billed.

Run with: python -m examples.nocweek
"""

from __future__ import annotations

from fleet.alertroute import Router
from fleet.catalog import Catalog, CatalogEntry
from fleet.objects import Node, Resources
from fleet.probes import Prober
from fleet.quarantine import Warden
from fleet.slo import SloBoard, SloSpec
from fleet.slofreeze import SloFreezeGate
from fleet.store import Store
from fleet.tickets import ToilLedger


def monday_setup() -> tuple[Store, Catalog, Router, SloBoard, Prober]:
    store = Store()
    for number in range(4):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    catalog = Catalog()
    catalog.register(
        CatalogEntry(
            deploy="checkout",
            team="payments",
            channel="#payments",
            escalation=("meera", "raj", "dana"),
        )
    )
    router = Router(catalog=catalog)
    board = SloBoard()
    board.watch(SloSpec(name="checkout", objective=0.99, window=5000))
    prober = Prober()
    prober.watch("checkout")
    return store, catalog, router, board, prober


def tuesday_outage(
    router: Router, board: SloBoard, prober: Prober
) -> None:
    for tick in range(200):
        if 100 <= tick < 140:
            board.observe("checkout", tick, good=40, total=100)
            prober.observe("checkout", tick, failure="timeout")
        else:
            board.observe("checkout", tick, good=100, total=100)
            prober.observe("checkout", tick, latency=20)
        if board.meters["checkout"].alarming(tick + 1):
            router.fire("slo-burn", "checkout", now=tick + 1)
    router.ack("slo-burn", "checkout")
    router.resolve("slo-burn", "checkout", now=200)
    print(
        f"tuesday: prober says {prober.targets['checkout'].verdict}, "
        f"{len(router.dispatches)} page(s) sent, first to "
        f"{router.dispatches[0].person}"
    )


def wednesday_freeze(board: SloBoard) -> SloFreezeGate:
    gate = SloFreezeGate(board=board)
    allowed, why = gate.may_ship("checkout")
    verdict = "ships" if allowed else "frozen"
    print(f"wednesday: checkout {verdict} ({why})")
    if not allowed:
        gate.break_glass("checkout", "meera", "revert the regression", now=300)
        allowed, why = gate.may_ship("checkout")
        print(f"wednesday: after the glass, ships ({why})")
    return gate


def thursday_hardware(store: Store, toil: ToilLedger) -> Warden:
    warden = Warden()
    warden.task_died(store, "n2", "checkout-1", "checkout", now=400)
    warden.task_died(store, "n2", "search-4", "search", now=405)
    outcome = warden.task_died(store, "n2", "cache-2", "cache", now=410)
    toil.log(410, "raj", "node-triage", 25, "confirmed n2 dimm errors")
    print(
        f"thursday: n2 {outcome}, schedulable={store.get_node('n2').schedulable}"
    )
    return warden


def friday_billing(toil: ToilLedger) -> None:
    toil.log(500, "meera", "manual-restart", 10, "checkout-3 wedged")
    toil.log(510, "dana", "node-triage", 15, "n7 fan noise")
    if "node-triage" in toil.candidates:
        toil.automate("node-triage", "quarantine warden")
    print("friday:")
    print(toil.report())


def main() -> int:
    store, _, router, board, prober = monday_setup()
    toil = ToilLedger()
    print("monday: 4 nodes up, checkout watched by probe, slo, and catalog")
    tuesday_outage(router, board, prober)
    wednesday_freeze(board)
    thursday_hardware(store, toil)
    friday_billing(toil)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
