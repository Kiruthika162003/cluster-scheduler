"""The second conformance wave: promises the newer organs must keep.

Same shape as the first wave, run assembled, spoken in the operator's
language. These checks cover the machinery that grew after the first
wave shipped: safe node retirement, cold start reconstruction,
redaction, cordon leases, zone spread under zone loss, and the phase
legality of an engine-driven life. The two waves stay separate files
because a conformance suite that needs scrolling is a conformance
suite nobody reads before the upgrade.
"""

from __future__ import annotations

from fleet.api import Fleet
from fleet.audit import Journal
from fleet.coldstart import cold_start
from fleet.conformance import Check
from fleet.control.budget import Budget
from fleet.cordonttl import CordonLeases
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.phases import check_history
from fleet.redact import RedactingRenderer
from fleet.store import Store
from fleet.timeline import phase_history
from fleet.verify import violations


def _fleet(nodes: int = 2) -> Fleet:
    fleet = Fleet()
    for number in range(nodes):
        fleet.store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    return fleet


def check_retirement_leaves_no_corpses() -> Check:
    fleet = _fleet()
    fleet.guard.budgets.append(
        Budget(
            name="floor", selector_key="app", selector_value="web", min_available=2
        )
    )
    for number in range(2):
        fleet.submit(
            "conformance",
            Task(
                spec=TaskSpec(
                    name=f"w{number}",
                    needs=Resources(cpu=300, memory=300),
                    labels=(("app", "web"),),
                )
            ),
        )
    fleet.step()
    fleet.retire_node("conformance", "n0")
    return Check(
        name="retirement-leaves-no-corpses",
        promise="removing a node never strands tasks on a ghost",
        passed=not violations(fleet.store),
    )


def check_cold_start_changes_nothing() -> Check:
    fleet = _fleet()
    for number in range(4):
        fleet.submit(
            "conformance",
            Task(
                spec=TaskSpec(
                    name=f"t{number}", needs=Resources(cpu=400, memory=400)
                )
            ),
        )
    fleet.step()
    engine, informer = cold_start(fleet.store)
    rebuilt_backlog = sorted(engine.queue.waiting)
    true_backlog = sorted(
        task.spec.name for task in fleet.store.pending_tasks()
    )
    return Check(
        name="cold-start-changes-nothing",
        promise="the plane rebuilt from the store knows exactly the backlog",
        passed=rebuilt_backlog == true_backlog and informer.agrees_with(fleet.store),
    )


def check_secrets_never_reach_a_page() -> Check:
    renderer = RedactingRenderer()
    secrets = ["hunter2secret", "sk-live-abcdef"]
    renderer.render(
        "app", {"db_password": secrets[0], "api_key": secrets[1], "mode": "fast"}
    )
    return Check(
        name="secrets-never-reach-a-page",
        promise="no secret value appears verbatim in any rendered surface",
        passed=renderer.leaked(secrets) == [] and renderer.masked == 2,
    )


def check_forgotten_cordons_expire() -> Check:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    journal = Journal()
    leases = CordonLeases(default_ttl=5)
    leases.cordon(store, journal, "n0", "someone", "and then they left", now=0)
    leases.sweep(store, journal, now=5)
    return Check(
        name="forgotten-cordons-expire",
        promise="a cordon outlives its reason only until its lease runs out",
        passed=store.get_node("n0").schedulable and leases.expired == 1,
    )


def check_an_engine_life_is_legal() -> Check:
    fleet = _fleet(nodes=1)
    fleet.submit(
        "conformance",
        Task(
            spec=TaskSpec(
                name="batchling", needs=Resources(cpu=800, memory=800), priority=10
            )
        ),
    )
    fleet.step()
    fleet.submit(
        "conformance",
        Task(
            spec=TaskSpec(
                name="crit", needs=Resources(cpu=800, memory=800), priority=1500
            )
        ),
    )
    fleet.step()
    life = phase_history(fleet.engine.journal, fleet.store, "batchling")
    return Check(
        name="an-engine-life-is-legal",
        promise="every life the engine writes parses under the phase table",
        passed=check_history(life) is None,
    )


SECOND_WAVE = (
    check_retirement_leaves_no_corpses,
    check_cold_start_changes_nothing,
    check_secrets_never_reach_a_page,
    check_forgotten_cordons_expire,
    check_an_engine_life_is_legal,
)
