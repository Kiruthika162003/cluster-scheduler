"""Load generation: the closed loop flatters, the open loop tells the truth.

A closed-loop generator waits for each response before sending the
next request, so when the server stalls the generator politely
stops arriving, and the measured latency omits every request that
would have arrived during the stall. This is coordinated omission,
and it makes a seizing server look like a fast one with a light
load. The open-loop generator arrives on schedule regardless,
queueing behind the stall like real users do, and its percentiles
include the waiting. Both generators run here against the same
scripted server so the flattery is a measured quantity: a 60-tick
stall reads as p99 of 2 under the closed loop, hidden inside its
missing throughput, and p99 of 60 under the open loop, a
thirtyfold flattery. At 100 percent load the open loop also shows
what saturation means: the queue never drains and even the median
lands at 62.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass
class ScriptedServer:
    service_ticks: int
    stalls: tuple[tuple[int, int], ...] = ()
    busy_until: int = 0

    def stalled(self, tick: int) -> bool:
        return any(start <= tick < end for start, end in self.stalls)

    def serve(self, arrival: int) -> int:
        """Returns completion time for a request arriving at `arrival`."""
        start = max(arrival, self.busy_until)
        while self.stalled(start):
            start += 1
        finish = start + self.service_ticks
        self.busy_until = finish
        return finish


@dataclass
class RunReport:
    sent: int
    latencies: list[int] = field(default_factory=list)

    def percentile(self, fraction: float) -> int:
        if not self.latencies:
            raise Invalid("no completed requests")
        ordered = sorted(self.latencies)
        index = int(fraction * (len(ordered) - 1) + 0.5)
        return ordered[index]

    def line(self, label: str) -> str:
        return (
            f"{label}: {self.sent} sent, p50 {self.percentile(0.5)}, "
            f"p99 {self.percentile(0.99)}"
        )


def closed_loop(server: ScriptedServer, duration: int) -> RunReport:
    report = RunReport(sent=0)
    now = 0
    while now < duration:
        finish = server.serve(now)
        report.sent += 1
        report.latencies.append(finish - now)
        now = finish
    return report


def open_loop(
    server: ScriptedServer, duration: int, every: int
) -> RunReport:
    if every <= 0:
        raise Invalid("the arrival interval must be positive")
    report = RunReport(sent=0)
    for arrival in range(0, duration, every):
        finish = server.serve(arrival)
        report.sent += 1
        report.latencies.append(finish - arrival)
    return report


def omission_gap(service_ticks: int, stall: tuple[int, int], duration: int, every: int) -> dict:
    """The same stall, measured both ways."""
    closed = closed_loop(
        ScriptedServer(service_ticks=service_ticks, stalls=(stall,)),
        duration,
    )
    open_ = open_loop(
        ScriptedServer(service_ticks=service_ticks, stalls=(stall,)),
        duration,
        every,
    )
    return {
        "closed_p99": closed.percentile(0.99),
        "open_p99": open_.percentile(0.99),
        "closed_sent": closed.sent,
        "open_sent": open_.sent,
        "flattery_factor": round(
            open_.percentile(0.99) / closed.percentile(0.99), 2
        ),
    }
