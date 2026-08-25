"""Region failover: west dies at breakfast, the workloads sort themselves.

Run with: python -m examples.regionfailover
"""

from __future__ import annotations

from fleet.errors import Unschedulable
from fleet.federation import Federator, Member
from fleet.objects import Node, Resources
from fleet.store import Store


def member(name: str, region: str, nodes: int) -> Member:
    store = Store()
    for number in range(nodes):
        store.add_node(
            Node(
                name=f"{name}-n{number}",
                capacity=Resources(cpu=1000, memory=1000),
            )
        )
    return Member(name=name, region=region, store=store)


def main() -> int:
    federator = Federator()
    federator.join(member("us-west", "us", nodes=3))
    federator.join(member("us-east", "us", nodes=2))
    federator.join(member("eu-central", "eu", nodes=2))

    workloads = [
        ("checkout", 800, None),
        ("search", 600, None),
        ("gdpr-ledger", 500, "eu"),
    ]
    for name, cpu, region in workloads:
        home = federator.place(name, cpu, region)
        print(f"{name} placed in {home}")

    print()
    print("us-west has a very bad morning")
    for name, cpu, region in workloads:
        if federator.placements.get(name) != "us-west":
            print(f"{name}: unaffected in {federator.placements[name]}")
            continue
        try:
            fresh = federator.fail_over(name, cpu, region)
            print(f"{name}: failed over to {fresh}")
        except Unschedulable as refused:
            print(f"{name}: STRANDED, {refused}")

    print()
    print(f"decision log: {len(federator.log)} entries, last three:")
    for line in federator.log[-3:]:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
