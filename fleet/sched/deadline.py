"""Deadline scheduling: the earliest deadline first, and what lateness costs.

Batch jobs carry durations and deadlines; one machine runs them in
some order. FIFO honours arrival, shortest-job-first honours the
impatient, and earliest-deadline-first honours the promise. The meter
is lateness, per job and at the worst, and the classic result holds in
the numbers: EDF minimises the maximum lateness on one machine, while
SJF minimises the queue's average wait and quietly lets the long job
with the near deadline burn.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BatchJob:
    name: str
    duration: int
    deadline: int


def run_order(jobs: list[BatchJob], policy: str) -> list[BatchJob]:
    if policy == "fifo":
        return list(jobs)
    if policy == "sjf":
        return sorted(jobs, key=lambda job: (job.duration, job.name))
    if policy == "edf":
        return sorted(jobs, key=lambda job: (job.deadline, job.name))
    raise ValueError(f"unknown policy {policy}")


def lateness_table(jobs: list[BatchJob], policy: str) -> dict[str, int]:
    clock = 0
    table = {}
    for job in run_order(jobs, policy):
        clock += job.duration
        table[job.name] = clock - job.deadline
    return table


def max_lateness(jobs: list[BatchJob], policy: str) -> int:
    return max(lateness_table(jobs, policy).values())


def jobs_late(jobs: list[BatchJob], policy: str) -> int:
    return sum(
        1 for lateness in lateness_table(jobs, policy).values() if lateness > 0
    )
