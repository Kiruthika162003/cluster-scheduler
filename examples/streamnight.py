"""A telemetry night: late events, folded history, one honest anomaly.

Run with: python -m examples.streamnight
"""

from __future__ import annotations

from fleet.outliers import compare
from fleet.rollup import Ladder
from fleet.seasonal import HOURS_PER_WEEK, SeasonalBaseline
from fleet.watermarks import WatermarkStream


def ingest_with_stragglers() -> WatermarkStream:
    stream = WatermarkStream(window_size=10, allowance=3)
    for event_time in range(0, 60, 2):
        stream.accept(event_time, value=5)
    stream.accept(33, value=5)
    stream.accept(4, value=5)
    return stream


def fold_the_history() -> Ladder:
    ladder = Ladder()
    for tick in range(2000):
        ladder.record(tick, 200.0 if tick == 100 else 1.0)
    return ladder


def judge_the_fleet() -> str:
    fleet = {f"n{number}": 10.0 + (number % 3) for number in range(9)}
    fleet["n9"] = 400.0
    return compare(fleet)


def judge_the_night() -> tuple[str, str]:
    baseline = SeasonalBaseline()
    for week in range(6):
        for hour in range(HOURS_PER_WEEK):
            value = 100.0 if hour % 24 < 6 else 1000.0
            baseline.learn(week * HOURS_PER_WEEK + hour, value)
    return baseline.judge(3, 102.0), baseline.judge(12, 450.0)


def main() -> int:
    stream = ingest_with_stragglers()
    print(f"ingest: {stream.report()}")
    ladder = fold_the_history()
    spike_alive = ladder.spike_survives(threshold=200.0)
    print(
        f"history: {ladder.footprint()} points held from 2000, "
        f"the 200.0 spike {'survives' if spike_alive else 'was erased'}"
    )
    print(f"fleet: {judge_the_fleet()}")
    quiet, hole = judge_the_night()
    print(f"3am at 102: {quiet}")
    print(f"noon at 450: {hole}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
