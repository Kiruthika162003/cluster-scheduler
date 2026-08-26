"""The ops review: five ledgers, one meeting, no feelings.

Run with: python -m examples.opsreview
"""

from __future__ import annotations

from fleet.changefail import DeliveryLedger
from fleet.inventory import LedgerEntry
from fleet.inventory import report as inventory_report
from fleet.libyear import FreshnessLedger
from fleet.mtbf import FailureLedger
from fleet.objects import Node, Resources
from fleet.patchcompliance import Advisory, ComplianceTracker
from fleet.store import Store


def reliability() -> str:
    ledger = FailureLedger(subject="checkout")
    ledger.record(started=100, repaired=110)
    ledger.record(started=200, repaired=230)
    ledger.record(started=500, repaired=520)
    return ledger.statement(until=1000)


def delivery() -> str:
    ledger = DeliveryLedger()
    for number, lead in enumerate((10, 12, 8, 40, 11)):
        shipped = 100 + number * 50
        ledger.shipped(f"d{number}", committed=shipped - lead, shipped=shipped)
    ledger.failed("d3", noticed=260, restored=290)
    return ledger.scorecard(window=250)


def security() -> str:
    tracker = ComplianceTracker()
    for number in range(3):
        tracker.node_runs(f"n{number}", "v1.2")
    tracker.node_runs("n3", "v1.3")
    tracker.publish(
        Advisory(
            name="CVE-1",
            severity="critical",
            affects=("v1.2",),
            published=100,
        )
    )
    return tracker.report(now=120)


def hardware() -> str:
    store = Store()
    for name in ("n0", "n1", "n9"):
        store.add_node(
            Node(name=name, capacity=Resources(cpu=1000, memory=1000))
        )
    ledger = [
        LedgerEntry(name=f"n{number}", cpu=1000, memory=1000)
        for number in range(4)
    ]
    return inventory_report(ledger, store)


def dependencies() -> str:
    ledger = FreshnessLedger()
    orm = ledger.track("ancient-orm")
    orm.released("1.0", at=0)
    orm.released("3.0", at=400)
    client = ledger.track("http-client")
    client.released("9.0", at=350)
    client.released("9.1", at=390)
    ledger.pin("ancient-orm", "1.0")
    ledger.pin("http-client", "9.0")
    return ledger.statement()


def main() -> int:
    print("reliability:", reliability())
    print()
    print("delivery:")
    print(delivery())
    print()
    print("security:")
    print(security())
    print()
    print("hardware:")
    print(hardware())
    print()
    print("dependencies:")
    print(dependencies())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
