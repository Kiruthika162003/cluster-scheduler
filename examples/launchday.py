"""Launch day: load climbs tenfold and two teams share one cluster.

Run with: python -m examples.launchday
"""

from __future__ import annotations

from fleet.autoscale import ReplicaScaler
from fleet.objects import Resources
from fleet.sched.quota import Drf, Team


def main() -> int:
    scaler = ReplicaScaler(floor=2, ceiling=40, step_limit=4, tolerance=1)
    current = 2
    path = [current]
    for hour, load in enumerate([150, 300, 700, 1500, 2800, 2800, 2600, 1200, 400]):
        current = scaler.wanted(current, float(load))
        path.append(current)
        del hour
    print(f"replica path through the launch: {path}")
    print(f"peak {max(path)} replicas against a ceiling of 40")

    cluster = Drf(
        capacity=Resources(cpu=40000, memory=80000),
        teams=[
            Team(name="web", shape=Resources(cpu=250, memory=250)),
            Team(name="batch", shape=Resources(cpu=100, memory=900)),
        ],
    )
    cluster.run_dry()
    for team in cluster.teams:
        share = cluster.dominant_share(team)
        print(
            f"{team.name}: {team.admitted} tasks admitted, "
            f"dominant share {share:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
