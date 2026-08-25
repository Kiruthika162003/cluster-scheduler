"""Fencing catches the one wake that matters; the lease prevents the rest.

The guess was three freezes producing three stale wakes and three
refusals. The measurement says one: controller A freezes three times,
but after the first freeze B holds the lease and renews it every
tick, so A never leads again and wakes from later freezes holding no
token at all. Only the first wake carries held-over work with a
stale token, and the fence refuses it with the token arithmetic
(1 < 2). The lease heals the recurring case by never letting the
flaky leader back; the fence exists for the single wake the lease
cannot prevent, and 291 legitimate writes land around one refusal.
"""

from __future__ import annotations

from fleet.leaderelect import Controller, Election, FencedLog
from fleet.trials.verdict import Verdict

FREEZES = ((40, 65), (140, 165), (240, 265))


def _frozen(tick: int) -> bool:
    return any(start <= tick < end for start, end in FREEZES)


def run() -> Verdict:
    election = Election()
    log = FencedLog()
    a = Controller(name="a", election=election, log=log)
    b = Controller(name="b", election=election, log=log)
    stale_attempts = 0
    for tick in range(300):
        if not _frozen(tick):
            woke_from_freeze = any(tick == end for _, end in FREEZES)
            if woke_from_freeze and a.token is not None:
                stale_attempts += 1
                log.write(f"held-over work at {tick}", a.token)
            a.tick(tick, work=f"a@{tick}")
        b.tick(tick, work=f"b@{tick}")
    numbers = {
        "handovers": len(election.handovers),
        "stale_attempts": stale_attempts,
        "fenced_writes": len(log.fenced),
        "accepted_writes": len(log.accepted),
    }
    holds = (
        numbers["handovers"] == 2
        and numbers["stale_attempts"] == 1
        and numbers["fenced_writes"] == 1
        and numbers["accepted_writes"] == 291
    )
    return Verdict(
        trial="fencerace",
        sentence=(
            "three freezes yield one stale wake, not three: the lease "
            "never lets the flaky leader back, and the fence refuses "
            "the one wake the lease cannot prevent"
        ),
        numbers=numbers,
        holds=holds,
    )
