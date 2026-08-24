"""One partition, one death, three watchers: the knob picks your poison.

East is partitioned alive for six ticks, heals, then dies for ten. The
eager watcher promotes on the first missed check and serves through
everything, paying six ticks of split brain while partitioned east
serves its side too. The patient watcher at three pays four. The
paranoid watcher at ten never promotes during the partition, pays zero
split brain, and pays nine ticks of outage when the real death comes.
The path dependence is the quiet finding: the eager watchers pay
nothing for the death at all, because the split brain they bought
during the partition had already moved the service to west, and the
death of a passive is free.
"""

from __future__ import annotations

from fleet.failover import partition_story
from fleet.trials.verdict import Verdict


def run() -> Verdict:
    eager = partition_story(promote_after=1)
    patient = partition_story(promote_after=3)
    paranoid = partition_story(promote_after=10)

    numbers = {
        "split_eager": eager.split_brain_ticks,
        "outage_eager": eager.outage_ticks,
        "split_patient": patient.split_brain_ticks,
        "outage_patient": patient.outage_ticks,
        "split_paranoid": paranoid.split_brain_ticks,
        "outage_paranoid": paranoid.outage_ticks,
        "promotions_each": (
            eager.watcher.promotions,
            patient.watcher.promotions,
            paranoid.watcher.promotions,
        ),
    }
    holds = (
        (eager.split_brain_ticks, eager.outage_ticks) == (6, 0)
        and (patient.split_brain_ticks, patient.outage_ticks) == (4, 0)
        and (paranoid.split_brain_ticks, paranoid.outage_ticks) == (0, 9)
        and numbers["promotions_each"] == (1, 1, 1)
    )
    return Verdict(
        trial="splitbrain",
        sentence=(
            "the eager watcher pays 6 ticks of split brain and no outage, "
            "the paranoid one 0 and 9, and the eager ones pay nothing for "
            "the later death because their split brain had already moved "
            "the service: the knob does not remove the poison, it picks "
            "one, and it also decides which failure you have already paid "
            "for when the next one arrives"
        ),
        numbers=numbers,
        holds=holds,
    )
