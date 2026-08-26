"""Work stealing: the idle worker's time buys the busy worker's backlog.

Static assignment goes wrong the moment tasks stop being equal:
one worker draws the long jobs and finishes an hour after its idle
peers. A stealing worker that runs dry takes work from the tail of
the busiest peer's queue, the tail because the head is about to
run and fighting over it buys contention instead of throughput.
Steals are counted and the comparison is the argument: a workload
whose long jobs all land on one worker finishes at 120 static and
60 with two steals, against a floor of 43 that atomic 30-tick jobs
keep out of reach. The gap between static and stealing is what the
thieves bought; the gap between stealing and the floor is what job
granularity still costs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass
class Worker:
    name: str
    queue: list[int] = field(default_factory=list)
    busy_until: int = 0
    done: int = 0

    def backlog(self) -> int:
        return sum(self.queue)


@dataclass
class StealingPool:
    workers: list[Worker]
    stealing: bool = True
    steals: int = 0

    def __post_init__(self) -> None:
        if not self.workers:
            raise Invalid("a pool needs workers")

    def assign(self, jobs: list[int]) -> None:
        for index, job in enumerate(jobs):
            self.workers[index % len(self.workers)].queue.append(job)

    def _steal_for(self, thief: Worker) -> bool:
        victim = max(self.workers, key=lambda worker: worker.backlog())
        if victim is thief or not victim.queue:
            return False
        thief.queue.append(victim.queue.pop())
        self.steals += 1
        return True

    def run(self) -> int:
        now = 0
        while True:
            for worker in self.workers:
                if worker.busy_until > now:
                    continue
                if not worker.queue and self.stealing:
                    self._steal_for(worker)
                if worker.queue:
                    job = worker.queue.pop(0)
                    worker.busy_until = now + job
                    worker.done += 1
            if all(
                not worker.queue and worker.busy_until <= now
                for worker in self.workers
            ):
                return now
            now += 1


def compare(jobs: list[int], worker_count: int) -> dict:
    if worker_count <= 0:
        raise Invalid("worker_count must be positive")
    static = StealingPool(
        workers=[Worker(name=f"w{i}") for i in range(worker_count)],
        stealing=False,
    )
    static.assign(jobs)
    static_finish = static.run()
    stealing = StealingPool(
        workers=[Worker(name=f"w{i}") for i in range(worker_count)],
        stealing=True,
    )
    stealing.assign(jobs)
    stealing_finish = stealing.run()
    floor = -(-sum(jobs) // worker_count)
    return {
        "static_finish": static_finish,
        "stealing_finish": stealing_finish,
        "floor": floor,
        "steals": stealing.steals,
        "bought": static_finish - stealing_finish,
    }
