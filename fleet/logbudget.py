"""Log budgets: observability has a bill, and sampling is how it gets paid.

Each namespace holds a lines-per-window budget. Under budget, every
line ships; over budget, the shipper samples at the ratio that would
have fit and stamps the stream with the sampling rate, because a
sampled stream that does not say so is a lie about frequency. Errors
are exempt from sampling by default, on the theory that the lines you
drop during an incident are the lines the incident was about.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LogBudget:
    lines_per_window: int
    window: int
    exempt_errors: bool = True
    shipped: int = 0
    sampled_out: int = 0
    history: dict[str, list[int]] = field(default_factory=dict)
    stamped: list[str] = field(default_factory=list)

    def _recent(self, namespace: str, now: int) -> list[int]:
        held = [
            tick
            for tick in self.history.get(namespace, [])
            if now - tick < self.window
        ]
        self.history[namespace] = held
        return held

    def offer(
        self, namespace: str, is_error: bool, now: int, sequence: int
    ) -> bool:
        recent = self._recent(namespace, now)
        if is_error and self.exempt_errors:
            recent.append(now)
            self.shipped += 1
            return True
        if len(recent) < self.lines_per_window:
            recent.append(now)
            self.shipped += 1
            return True
        overrun = len(recent) + 1
        keep_one_in = max(2, overrun // self.lines_per_window + 1)
        if sequence % keep_one_in == 0:
            recent.append(now)
            self.shipped += 1
            stamp = f"{namespace}: sampling 1 in {keep_one_in}"
            if stamp not in self.stamped:
                self.stamped.append(stamp)
            return True
        self.sampled_out += 1
        return False
