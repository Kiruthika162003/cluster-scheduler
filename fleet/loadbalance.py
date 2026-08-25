"""Endpoint picking: round robin, random, and the two random choices.

The balancer picks which endpoint serves each request. Round robin is
fair in arrivals and blind to service times; pure random is worse and
cheaper; and two-random-choices peeks at the queue depth of two random
endpoints and takes the shorter, which is nearly as cheap as random
and nearly as good as tracking everything. The meter is the worst
queue depth over the run, because tail latency lives wherever the
deepest queue is, and the trial runs all three on the same skewed
service times.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class Endpoint:
    name: str
    service_ticks: int
    queue: int = 0
    served: int = 0

    def offer(self) -> None:
        self.queue += 1

    def work(self, now: int) -> None:
        if now % self.service_ticks == 0 and self.queue > 0:
            self.queue -= 1
            self.served += 1


@dataclass
class Balancer:
    policy: str
    endpoints: list[Endpoint]
    seed: int = 7
    cursor: int = 0
    worst_depth: int = 0
    source: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self.source = random.Random(self.seed)

    def pick(self) -> Endpoint:
        if self.policy == "round-robin":
            chosen = self.endpoints[self.cursor % len(self.endpoints)]
            self.cursor += 1
            return chosen
        if self.policy == "random":
            return self.source.choice(self.endpoints)
        first, second = self.source.sample(self.endpoints, 2)
        return first if first.queue <= second.queue else second

    def tick(self, now: int, arrivals: int) -> None:
        for _ in range(arrivals):
            self.pick().offer()
        for endpoint in self.endpoints:
            endpoint.work(now)
            self.worst_depth = max(self.worst_depth, endpoint.queue)
