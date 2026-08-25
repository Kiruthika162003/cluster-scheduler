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
    joined_at: int = 0
    cold_period: int = 0
    cold_for: int = 0

    def offer(self) -> None:
        self.queue += 1

    def _period(self, now: int) -> int:
        if self.cold_for and now - self.joined_at < self.cold_for:
            return self.cold_period or self.service_ticks
        return self.service_ticks

    def work(self, now: int) -> None:
        if now % self._period(now) == 0 and self.queue > 0:
            self.queue -= 1
            self.served += 1


@dataclass
class Balancer:
    policy: str
    endpoints: list[Endpoint]
    seed: int = 7
    slow_start: int = 0
    now: int = 0
    cursor: int = 0
    worst_depth: int = 0
    source: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self.source = random.Random(self.seed)

    def _ramp_weight(self, endpoint: Endpoint) -> float:
        if not self.slow_start:
            return 1.0
        age = self.now - endpoint.joined_at
        return min(1.0, max(0.1, age / self.slow_start))

    def pick(self) -> Endpoint:
        if self.policy == "round-robin":
            for _ in range(len(self.endpoints)):
                chosen = self.endpoints[self.cursor % len(self.endpoints)]
                self.cursor += 1
                ramp = self._ramp_weight(chosen)
                if ramp >= 1.0 or self.source.random() <= ramp:
                    return chosen
            return chosen
        if self.policy == "random":
            return self.source.choice(self.endpoints)
        first, second = self.source.sample(self.endpoints, 2)
        chosen = first if first.queue <= second.queue else second
        ramp = self._ramp_weight(chosen)
        if ramp < 1.0 and self.source.random() > ramp:
            return second if chosen is first else first
        return chosen

    def tick(self, now: int, arrivals: int) -> None:
        self.now = now
        for _ in range(arrivals):
            self.pick().offer()
        for endpoint in self.endpoints:
            endpoint.work(now)
            self.worst_depth = max(self.worst_depth, endpoint.queue)
