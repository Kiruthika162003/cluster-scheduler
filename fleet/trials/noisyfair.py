"""Fair sharing under overcommit pays the greedy three to one, measured.

Two honest tenants request 300 and use 300; a noisy one requests 200
and uses 900 on a 1000 node. Fair scarcity slows everyone to two
thirds: the honest pair each finish 20000 work-ticks of a possible
30000 while the tenant who asked for the least finishes 60000. Asking
honestly is the losing move under uncapped sharing, which is the
quiet scandal of the arrangement. Capping the noisy tenant at its own
request restores everything: the honest pair get their full 30000, the
noisy gets exactly the 20000 it asked for, and nobody was evicted; the
cap is the eviction that keeps the tenant.
"""

from __future__ import annotations

from fleet.interference import SharedNode, Tenant
from fleet.trials.verdict import Verdict


def _node(capped: bool) -> SharedNode:
    node = SharedNode(capacity=1000)
    node.tenants = [
        Tenant(name="steady-a", requested=300, using=300),
        Tenant(name="steady-b", requested=300, using=300),
        Tenant(name="noisy", requested=200, using=900, capped=capped),
    ]
    node.run(100)
    return node


def run() -> Verdict:
    wild = _node(capped=False)
    tame = _node(capped=True)

    numbers = {
        "slowdown_uncapped": round(wild.slowdown(), 3),
        "steady_work_uncapped": round(wild.victim_throughput("steady-a")),
        "noisy_work_uncapped": round(wild.victim_throughput("noisy")),
        "steady_work_capped": round(tame.victim_throughput("steady-a")),
        "noisy_work_capped": round(tame.victim_throughput("noisy")),
    }
    holds = (
        numbers["slowdown_uncapped"] == 0.667
        and numbers["steady_work_uncapped"] == 20000
        and numbers["noisy_work_uncapped"] == 60000
        and numbers["steady_work_capped"] == 30000
        and numbers["noisy_work_capped"] == 20000
        and tame.slowdown() == 1.0
    )
    return Verdict(
        trial="noisyfair",
        sentence=(
            "uncapped fair sharing pays the tenant who requested least "
            "60000 work-ticks while the honest pair get 20000 each; the "
            "cap at request restores the full 30000 to the honest and "
            "hands the noisy exactly what it asked for, with nobody "
            "evicted"
        ),
        numbers=numbers,
        holds=holds,
    )
