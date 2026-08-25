"""Pre-scaling the nightly batch: the queue is bought, not eliminated.

Three nights of a 900-unit burst against a 300-unit base. Reactive
scaling adds capacity five ticks after each firing and the backlog
integral costs 2700 work-ticks of queued batch across the nights.
Pre-scaling from the cron table serves every burst instantly, zero
queued, and the bill moves to 19800 idle capacity-ticks of warm spare
metal, 7.3 times the queued work it removed, in a different currency.
Neither number is wrong; the trial's job is to make sure whoever picks
is looking at both.
"""

from __future__ import annotations

from fleet.control.cron import Schedule
from fleet.control.jobs import JobSpec
from fleet.objects import Resources, TaskSpec
from fleet.prescale import Prescaler, queued_work
from fleet.trials.verdict import Verdict

BASE = 300
BURST = 900
FIRES = (0, 100, 200)


def _schedule() -> Schedule:
    job = JobSpec(
        name="batch",
        completions=1,
        parallelism=1,
        template=TaskSpec(name="tpl", needs=Resources(cpu=1, memory=1)),
    )
    return Schedule(name="batch", every=100, job=job)


def _reactive(tick: int) -> int:
    for fire in FIRES:
        if fire <= tick < fire + 5:
            return BASE
        if fire + 5 <= tick < fire + 20:
            return BASE + BURST
    return BASE


def run() -> Verdict:
    prescaler = Prescaler(warmup=5)
    prescaler.plan([_schedule()], demand_cpu=BURST, horizon=250)

    def prescaled(tick: int) -> int:
        return prescaler.capacity_at(BASE, tick)

    reactive_queued = sum(
        queued_work(BURST, fire, fire + 30, _reactive) for fire in FIRES
    )
    prescale_queued = sum(
        queued_work(BURST, fire, fire + 30, prescaled) for fire in FIRES
    )
    provisioned = sum(
        max(0, prescaled(tick) - BASE) for tick in range(250)
    )
    idle = provisioned - BURST * len(FIRES)

    numbers = {
        "queued_reactive": reactive_queued,
        "queued_prescaled": prescale_queued,
        "idle_capacity_ticks": idle,
        "exchange_rate": round(idle / reactive_queued, 1),
    }
    holds = (
        reactive_queued == 2700
        and prescale_queued == 0
        and idle == 19800
    )
    return Verdict(
        trial="nightshift",
        sentence=(
            "reactive scaling queues 2700 work-ticks of batch across "
            "three nights; pre-scaling from the cron table queues zero "
            "and pays 19800 idle capacity-ticks instead, 7.3 to one in a "
            "different currency, which is why it is a choice and not a "
            "free win"
        ),
        numbers=numbers,
        holds=holds,
    )
