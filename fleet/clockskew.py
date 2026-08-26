"""Clock skew: distributed time is an estimate wearing a wristwatch.

Two nodes disagree about now by some unknown amount, and every
cross-node timestamp comparison silently bets that amount is zero.
The skew tracker estimates each peer's offset from echo exchanges:
send at T1, peer stamps T2, reply lands at T3; the offset estimate
is T2 minus the midpoint, and its error bound is half the round
trip, because the stamp could have happened anywhere inside it.
Comparisons then come with honesty attached: ordered() answers yes,
no, or too-close-to-call when the gap sits inside the combined
error, and the too-close answer is the load-bearing one, since the
confident wrong answer is how cross-node event logs lie. Bounds
grow with silence since drift accumulates, so an estimate is a
perishable good with its age printed on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid

DRIFT_PER_TICK = 0.002


@dataclass
class SkewEstimate:
    offset: float
    error: float
    measured_at: int

    def error_at(self, now: int) -> float:
        return round(self.error + (now - self.measured_at) * DRIFT_PER_TICK, 4)


@dataclass
class SkewTracker:
    estimates: dict[str, SkewEstimate] = field(default_factory=dict)

    def echo(self, peer: str, sent: int, peer_stamp: int, received: int) -> SkewEstimate:
        if received < sent:
            raise Invalid("the reply cannot land before the request left")
        round_trip = received - sent
        midpoint = sent + round_trip / 2
        estimate = SkewEstimate(
            offset=round(peer_stamp - midpoint, 4),
            error=round(round_trip / 2, 4),
            measured_at=received,
        )
        self.estimates[peer] = estimate
        return estimate

    def to_local(self, peer: str, stamp: int, now: int) -> tuple[float, float]:
        if peer not in self.estimates:
            raise Invalid(f"{peer} has no skew estimate")
        held = self.estimates[peer]
        return round(stamp - held.offset, 4), held.error_at(now)

    def ordered(
        self,
        first_peer: str,
        first_stamp: int,
        second_peer: str,
        second_stamp: int,
        now: int,
    ) -> str:
        first_local, first_error = self.to_local(first_peer, first_stamp, now)
        second_local, second_error = self.to_local(
            second_peer, second_stamp, now
        )
        gap = second_local - first_local
        blur = first_error + second_error
        if gap > blur:
            return "yes"
        if gap < -blur:
            return "no"
        return "too close to call"

    def report(self, now: int) -> str:
        if not self.estimates:
            return "no peers measured"
        lines = []
        for peer in sorted(self.estimates):
            held = self.estimates[peer]
            lines.append(
                f"{peer}: offset {held.offset:+} within "
                f"{held.error_at(now)} (measured at {held.measured_at})"
            )
        return "\n".join(lines)
