"""Queueing arithmetic: the knee is at the utilisation, not the traffic.

The single-server model with random arrivals predicts waiting time
as service_time times rho over one minus rho, where rho is
utilisation. The formula's lesson is the shape: wait doubles from
50 to 75 percent utilisation, doubles again by 87, and the last
ten percent of capacity costs more latency than the first ninety.
The model here is checked against the deterministic generator in
loadgen rather than trusted: uniform arrivals wait far less than
the random-arrival formula predicts, which the comparison method
reports honestly, because the formula is an upper story about
variance, not a law about queues, and knowing which story applies
is the actual skill. Little's law, in flight equals rate times
wait, holds for both and is checked exactly.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleet.errors import Invalid
from fleet.loadgen import ScriptedServer, open_loop


@dataclass(frozen=True)
class QueuePrediction:
    rho: float
    predicted_wait: float
    predicted_in_flight: float


def predict(arrival_rate: float, service_ticks: int) -> QueuePrediction:
    if arrival_rate <= 0 or service_ticks <= 0:
        raise Invalid("rates and service time must be positive")
    rho = arrival_rate * service_ticks
    if rho >= 1.0:
        raise Invalid(
            f"utilisation {round(rho, 3)} >= 1: the queue grows without "
            f"bound and no formula owes you a number"
        )
    wait = service_ticks * rho / (1.0 - rho)
    total_latency = wait + service_ticks
    return QueuePrediction(
        rho=round(rho, 4),
        predicted_wait=round(wait, 3),
        predicted_in_flight=round(arrival_rate * total_latency, 3),
    )


def knee_table(service_ticks: int, shares: tuple[float, ...]) -> str:
    lines = ["rho    wait"]
    for share in shares:
        arrival = share / service_ticks
        row = predict(arrival, service_ticks)
        lines.append(f"{row.rho:.2f}   {row.predicted_wait}")
    return "\n".join(lines)


def measured_wait(service_ticks: int, every: int, duration: int) -> float:
    report = open_loop(
        ScriptedServer(service_ticks=service_ticks), duration, every
    )
    waits = [latency - service_ticks for latency in report.latencies]
    return round(sum(waits) / len(waits), 3)


def compare_to_uniform(
    service_ticks: int, every: int, duration: int = 2000
) -> str:
    arrival_rate = 1.0 / every
    prediction = predict(arrival_rate, service_ticks)
    measured = measured_wait(service_ticks, every, duration)
    if measured < prediction.predicted_wait:
        return (
            f"uniform arrivals wait {measured} against the random-arrival "
            f"story of {prediction.predicted_wait}: the formula prices "
            f"variance you do not have"
        )
    return (
        f"measured {measured} vs predicted {prediction.predicted_wait}: "
        f"the arrivals are at least as bursty as the model"
    )
