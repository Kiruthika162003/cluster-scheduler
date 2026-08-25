"""The flight recorder: every tick's meters, and the twin-run determinism proof.

The recorder samples the sim's meters after every tick into a trace.
Two uses: regression, a saved trace pinned in a test fails the moment
any refactor changes one number at one tick; and the determinism
proof, two runs of the same scenario must produce byte-identical
traces, which is the property every debugging session in this package
quietly leans on. Divergence reports the first differing tick and
both values, because a diff that says traces differ is a shrug.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.sim.cluster import Sim


@dataclass
class Trace:
    rows: list[tuple[int, int, int, int, int]] = field(default_factory=list)

    def sample(self, sim: Sim) -> None:
        self.rows.append(
            (
                sim.now,
                sim.running_count(),
                sim.serving_count(),
                len(sim.store.nodes),
                sim.monitor.evicted,
            )
        )

    def first_divergence(self, other: Trace) -> str | None:
        for mine, theirs in zip(self.rows, other.rows, strict=False):
            if mine != theirs:
                return (
                    f"tick {mine[0]}: {mine} against {theirs}"
                )
        if len(self.rows) != len(other.rows):
            return (
                f"lengths differ: {len(self.rows)} against {len(other.rows)}"
            )
        return None


def record(sim: Sim, ticks: int) -> Trace:
    trace = Trace()
    for _ in range(ticks):
        sim.tick()
        trace.sample(sim)
    return trace
