"""Game day: twenty five storms, the worst one replayed, the brief written.

Run with: python -m examples.gameday
"""

from __future__ import annotations

from fleet.audit import Journal
from fleet.chaos import Chaos
from fleet.control.deploy import DeploySpec
from fleet.objects import Resources, TaskSpec
from fleet.oncall import brief
from fleet.sim.cluster import Script, Sim


def main() -> int:
    chaos = Chaos()
    floor = chaos.campaign(seeds=25)
    worst = chaos.worst_storm()
    print(f"campaign floor across 25 storms: {floor} of 8 truthfully serving")
    print(
        f"worst storm: seed {worst.seed}, silences {worst.silences}, "
        f"{worst.evictions} evictions"
    )

    replay = chaos._storm(worst.seed)
    print(f"replayed seed {worst.seed}: truthful floor {replay.truthful} "
          f"(campaign said {worst.truthful})")

    sim_journal = Journal()
    sim_journal.note(0, "gameday", "campaign", "run", "25 seeded storms")
    sim_journal.note(1, "gameday", f"seed-{worst.seed}", "replay", "worst storm verified")
    sim = Sim(script=Script(silences=worst.silences))
    sim.add_nodes(5)
    sim.deploys.append(
        DeploySpec(
            name="web",
            replicas=8,
            template=TaskSpec(name="tpl", needs=Resources(cpu=300, memory=300)),
        )
    )
    sim.run(120)
    page = brief(
        sim.store,
        sim_journal,
        since=0,
        running=sim.running_count(),
        serving=sim.serving_count(),
    )
    print()
    print(page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
