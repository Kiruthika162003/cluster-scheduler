"""Memory buys accuracy on a curve that flattens faster than guessed.

The same 10000-sample stream through reservoirs of 50, 500, and
2000 slots, median error measured against the exact answer. The
guess was a smooth curve, 3.63 to 0.81 to 0.35; the measurement
says 4.28, 0.81, 0.79: the first tenfold spend buys a 5.3x error
cut and the next quadrupling buys two hundredths of a point,
statistically nothing. The knee sits at the middle size, and past
it memory stops buying accuracy and starts buying the feeling of
accuracy.
"""

from __future__ import annotations

from fleet.quantilesketch import measured_error
from fleet.trials.verdict import Verdict

STREAM = [float((7919 * number) % 10000) for number in range(10000)]
SIZES = (50, 500, 2000)


def run() -> Verdict:
    errors = {
        size: measured_error(STREAM, size=size, fraction=0.5)
        for size in SIZES
    }
    numbers = {f"median_error_at_{size}": errors[size] for size in SIZES}
    holds = (
        errors[50] == 4.28
        and errors[500] == 0.81
        and errors[2000] == 0.79
        and errors[50] > errors[500] > errors[2000]
    )
    return Verdict(
        trial="sketchbill",
        sentence=(
            "50 slots err 4.28 points, 500 err 0.81, 2000 err 0.79: "
            "the next quadrupling buys two hundredths of a point"
        ),
        numbers=numbers,
        holds=holds,
    )
