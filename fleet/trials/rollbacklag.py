"""The dial controls arrivals; the population obeys the sessions.

Thirty percent of new sessions go to the canary, sessions last twenty
ticks, and at tick 60 the dial slams to zero. The canary population is
28.5 percent one tick later, 13.5 percent ten ticks later, and reaches
zero only at tick 79: nineteen ticks of the rolled-back build serving
every user it had already caught. Rollback is not an event, it is a
drain with the session length as its clock, and any incident timeline
that marks recovery at the dial is early by one session.
"""

from __future__ import annotations

from fleet.roll.traffic import Splitter
from fleet.trials.verdict import Verdict


def run() -> Verdict:
    splitter = Splitter(canary_share=0.3, session_length=20)
    shares = []
    for now in range(120):
        if now == 60:
            splitter.canary_share = 0.0
        splitter.tick(now, new_users=10)
        shares.append(round(splitter.canary_population_share(), 3))

    clean_at = next(
        (tick for tick, share in enumerate(shares) if tick > 60 and share == 0.0),
        None,
    )
    numbers = {
        "steady_share": shares[30],
        "share_after_rollback": shares[60],
        "share_ten_later": shares[70],
        "clean_at": clean_at,
        "drain_ticks": None if clean_at is None else clean_at - 60,
    }
    holds = (
        shares[30] == 0.3
        and shares[60] == 0.285
        and shares[70] == 0.135
        and clean_at == 79
    )
    return Verdict(
        trial="rollbacklag",
        sentence=(
            "the dial hits zero at tick 60 and the canary population "
            "reaches zero at 79: nineteen ticks of the rolled-back build "
            "serving the users it caught, so recovery marked at the dial "
            "is early by one session length"
        ),
        numbers=numbers,
        holds=holds,
    )
