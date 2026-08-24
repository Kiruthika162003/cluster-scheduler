"""The wrong probe type turns a warmup into a crashloop, tick by tick.

A task takes eight ticks to warm its caches, during which it cannot
serve. Wired as a readiness probe, the warmup costs eight ticks out of
traffic and zero restarts: the task finishes warming and joins. Wired
as a liveness probe, every warmup tick is a failed check: the keeper
kills it at the failure threshold, the restart begins another warmup,
the backoff stretches the gaps, and the task is still crashlooping at
tick sixty having served nothing. Same task, same eight tick warmup,
and the only difference is which probe the config named.
"""

from __future__ import annotations

from fleet.control.endpoints import Readiness, Service, endpoints
from fleet.control.health import Keeper, Probe
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store
from fleet.trials.verdict import Verdict

WARMUP = 8


def _store() -> Store:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    task = Task(
        spec=TaskSpec(
            name="warmer",
            needs=Resources(cpu=100, memory=100),
            labels=(("app", "web"),),
        )
    )
    task.bound_to("n0")
    store.add_task(task)
    return store


def _as_readiness() -> tuple[int, int, int]:
    """(restarts, ticks out of traffic, first serving tick)."""
    store = _store()
    store.get_task("warmer").phase = "Running"
    service = Service(name="svc", selector_key="app", selector_value="web")
    readiness = Readiness(
        unready_at={"warmer": frozenset(range(WARMUP))}
    )
    out_of_traffic = 0
    first_serving = None
    for now in range(60):
        served = endpoints(store, service, readiness, now)
        if not served:
            out_of_traffic += 1
        elif first_serving is None:
            first_serving = now
    return store.get_task("warmer").restarts, out_of_traffic, first_serving


def _as_liveness() -> tuple[int, int]:
    """(restarts by tick 60, ticks spent Running)."""
    store = _store()
    keeper = Keeper(
        probes={"warmer": Probe(failing_attempts=frozenset(range(100)))}
    )
    running_ticks = 0
    for now in range(60):
        keeper.tick(store, now)
        if store.get_task("warmer").phase == "Running":
            running_ticks += 1
    return store.get_task("warmer").restarts, running_ticks


def run() -> Verdict:
    ready_restarts, out_of_traffic, first_serving = _as_readiness()
    live_restarts, running_ticks = _as_liveness()

    numbers = {
        "readiness_restarts": ready_restarts,
        "readiness_ticks_out": out_of_traffic,
        "readiness_first_serving": first_serving,
        "liveness_restarts_by_60": live_restarts,
        "liveness_running_ticks": running_ticks,
    }
    holds = (
        ready_restarts == 0
        and out_of_traffic == WARMUP
        and first_serving == WARMUP
        and live_restarts >= 5
        and running_ticks == 0
    )
    return Verdict(
        trial="wrongprobe",
        sentence=(
            "the warmup wired as readiness costs eight ticks out of "
            "traffic and zero restarts; wired as liveness it is killed "
            "into a backoff crashloop that has served zero ticks by tick "
            "sixty, and the only difference is which probe the config "
            "named"
        ),
        numbers=numbers,
        holds=holds,
    )
