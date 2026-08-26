"""The knee is real, but bursts build it, not the load average.

The generator drives the scripted server at rising utilisation,
first with uniform arrivals, then with the same average rate
arriving in bursts of four. Uniform arrivals never queue at any
utilisation below one: mean wait 0.0 at rho 0.5, 0.75, and 0.9,
because a deterministic world has no variance to pay for. The
bursty runs at identical average rates wait exactly 1.5 service
times at every rho, 3.0, 4.5, and 13.5 ticks, the fixed cost of
standing four-deep at the counter, and the formula's smooth knee
sits between the two worlds. The lesson the
pair of rows makes unavoidable: utilisation alone predicts nothing
until you know how the arrivals clump, and the clumping, not the
load average, is what the knee is made of.
"""

from __future__ import annotations

from fleet.loadgen import RunReport, ScriptedServer
from fleet.trials.verdict import Verdict

RHOS = ((2, 4), (3, 4), (9, 10))


def _uniform_wait(busy: int, cycle: int) -> float:
    server = ScriptedServer(service_ticks=busy)
    report = RunReport(sent=0)
    for arrival in range(0, 2000, cycle):
        finish = server.serve(arrival)
        report.sent += 1
        report.latencies.append(finish - arrival - busy)
    return round(sum(report.latencies) / len(report.latencies), 2)


def _bursty_wait(busy: int, cycle: int) -> float:
    server = ScriptedServer(service_ticks=busy)
    waits = []
    for burst_start in range(0, 2000, cycle * 4):
        for _ in range(4):
            finish = server.serve(burst_start)
            waits.append(finish - burst_start - busy)
    return round(sum(waits) / len(waits), 2)


def run() -> Verdict:
    numbers = {}
    for busy, cycle in RHOS:
        rho = busy / cycle
        numbers[f"uniform_rho_{rho}"] = _uniform_wait(busy, cycle)
        numbers[f"bursty_rho_{rho}"] = _bursty_wait(busy, cycle)
    holds = (
        all(numbers[f"uniform_rho_{busy / cycle}"] == 0.0 for busy, cycle in RHOS)
        and all(
            numbers[f"bursty_rho_{busy / cycle}"]
            == round(1.5 * busy, 2)
            for busy, cycle in RHOS
        )
    )
    return Verdict(
        trial="queueknee",
        sentence=(
            "uniform arrivals wait zero at every rho below one; the same "
            "rates in bursts of four wait 1.5 service times, and the "
            "clumping, not the load average, is what the knee is made of"
        ),
        numbers=numbers,
        holds=holds,
    )
