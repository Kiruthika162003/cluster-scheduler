"""Two teams, one cluster: hooks shape, quotas gate, the page tells.

Run with: python -m examples.multiteam
"""

from __future__ import annotations

from fleet.control.hooks import Chain, default_labels, minimum_resources, require_label
from fleet.control.nsquota import Admission, NamespaceQuota
from fleet.errors import Invalid
from fleet.objects import Resources, Task, TaskSpec
from fleet.store import Store
from fleet.tenancyreport import quota_map, rendered, standard_quota


def main() -> int:
    chain = Chain()
    chain.mutate_with("team-default", default_labels(team="unassigned"))
    chain.mutate_with("floors", minimum_resources(cpu=50, memory=50))
    chain.validate_with("must-have-team", require_label("team"))

    gate = Admission(
        quotas={
            "search": NamespaceQuota(
                namespace="search",
                max_tasks=4,
                max_requests=Resources(cpu=1000, memory=2000),
            ),
            "ads": NamespaceQuota(
                namespace="ads",
                max_tasks=10,
                max_requests=Resources(cpu=600, memory=1200),
            ),
        }
    )
    store = Store()

    submissions = [
        ("search", "indexer", 300),
        ("search", "crawler", 300),
        ("search", "ranker", 300),
        ("ads", "bidder", 200),
        ("ads", "pacer", 200),
        ("ads", "greedy", 500),
        ("search", "tiny", 10),
    ]
    for namespace, name, cpu in submissions:
        spec = TaskSpec(
            name=name,
            needs=Resources(cpu=cpu, memory=cpu),
            namespace=namespace,
        )
        shaped = chain.admit(spec)
        try:
            gate.admit(store, Task(spec=shaped))
            print(f"admitted {namespace}/{name} at {shaped.needs.cpu}m")
        except Invalid as refused:
            print(f"refused {namespace}/{name}: {refused}")

    print()
    print(
        rendered(
            store,
            quota_map(
                standard_quota("search", cpu=1000), standard_quota("ads", cpu=600)
            ),
        )
    )
    print(f"hook trace: {len(chain.trace)} entries, refusals {gate.refused}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
