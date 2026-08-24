"""What actually stops replica flapping: not the damper, the deadband.

The guess was that the step limit reduces churn. Measured, it does not:
on a square wave of load both scalers spend exactly 180 replica-moves in
400 ticks, because damping spreads the same journey over more ticks. It
does cap the jump size, 18 at an edge versus 2. What kills churn on a
noisy plateau is the deadband: targets wobbling between 10 and 12 drive
598 moves with no tolerance and exactly zero with a tolerance of two.
"""

from __future__ import annotations

from fleet.autoscale import ReplicaScaler
from fleet.trials.verdict import Verdict


def _square(tick: int) -> float:
    return 1400.0 if (tick // 40) % 2 == 0 else 100.0


def _noisy(tick: int) -> float:
    wiggle = (0, 60, -50, 80, -70, 30, -40, 90)[tick % 8]
    return 700.0 + wiggle


def _drive(load, start: int, **kw) -> tuple[int, int]:
    scaler = ReplicaScaler(floor=2, ceiling=24, **kw)
    current = start
    flaps = biggest = 0
    for tick in range(400):
        wanted = scaler.wanted(current, load(tick))
        flaps += abs(wanted - current)
        biggest = max(biggest, abs(wanted - current))
        current = wanted
    return flaps, biggest


def run() -> Verdict:
    square_wild, square_wild_jump = _drive(_square, start=2, step_limit=100)
    square_calm, square_calm_jump = _drive(_square, start=2, step_limit=2)
    noise_bare, _ = _drive(_noisy, start=10, step_limit=100)
    noise_damped, _ = _drive(_noisy, start=10, step_limit=2)
    noise_dead, _ = _drive(_noisy, start=10, step_limit=100, tolerance=2)

    numbers = {
        "square_flaps_undamped": square_wild,
        "square_flaps_damped": square_calm,
        "square_jump_undamped": square_wild_jump,
        "square_jump_damped": square_calm_jump,
        "noise_flaps_bare": noise_bare,
        "noise_flaps_damped": noise_damped,
        "noise_flaps_deadband": noise_dead,
    }
    holds = (
        square_wild == square_calm == 180
        and square_wild_jump == 18
        and square_calm_jump == 2
        and noise_bare == noise_damped == 598
        and noise_dead == 0
    )
    return Verdict(
        trial="oscillation",
        sentence=(
            "the step limit never reduced churn, 180 moves either way on "
            "the square wave and 598 on the noisy plateau; it only caps "
            "the jump at 2 instead of 18, while a deadband of two "
            "replicas takes the plateau's 598 moves to zero"
        ),
        numbers=numbers,
        holds=holds,
    )
