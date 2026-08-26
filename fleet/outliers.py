"""Outlier detection: the median does not flinch when the mean faints.

One node reporting 40x latency drags the fleet mean so far that
z-scores judge every healthy node abnormal and the sick one barely
so; the mean-based detector is broken exactly when it is needed.
Robust detection uses the median and the median absolute deviation,
both of which ignore the outlier while measuring it, and flags
values whose robust score crosses the threshold. The comparison is
kept as a method because it is the argument: on a ten-node fleet
with one 40x spike, the z-score flags nothing at three sigma, the
spike having inflated sigma enough to hide itself, while the robust
score flags it at 262, and the docstring's job is to make that
difference impossible to unlearn. Ties and tiny fleets are
handled by refusing to judge rather than judging badly.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleet.errors import Invalid

ROBUST_THRESHOLD = 3.5
CONSISTENCY = 1.4826


def median(values: list[float]) -> float:
    if not values:
        raise Invalid("no values")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def mad(values: list[float]) -> float:
    center = median(values)
    return median([abs(value - center) for value in values])


@dataclass(frozen=True)
class Outlier:
    name: str
    value: float
    robust_score: float


def robust_outliers(
    samples: dict[str, float], threshold: float = ROBUST_THRESHOLD
) -> list[Outlier]:
    if len(samples) < 4:
        raise Invalid("outlier detection needs at least four samples")
    values = list(samples.values())
    center = median(values)
    spread = mad(values) * CONSISTENCY
    if spread == 0:
        distinct = {value for value in values if value != center}
        return sorted(
            (
                Outlier(name=name, value=value, robust_score=float("inf"))
                for name, value in samples.items()
                if value in distinct
            ),
            key=lambda outlier: outlier.name,
        )
    found = []
    for name, value in sorted(samples.items()):
        score = abs(value - center) / spread
        if score >= threshold:
            found.append(
                Outlier(name=name, value=value, robust_score=round(score, 2))
            )
    return found


def zscore_outliers(
    samples: dict[str, float], threshold: float = 3.0
) -> list[str]:
    """The mean-based detector, kept for the comparison it loses."""
    if len(samples) < 4:
        raise Invalid("outlier detection needs at least four samples")
    values = list(samples.values())
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    deviation = variance**0.5
    if deviation == 0:
        return []
    return sorted(
        name
        for name, value in samples.items()
        if abs(value - mean) / deviation >= threshold
    )


def compare(samples: dict[str, float]) -> str:
    robust = robust_outliers(samples)
    naive = zscore_outliers(samples)
    return (
        f"robust flags {[outlier.name for outlier in robust]}, "
        f"z-score flags {naive}"
    )
