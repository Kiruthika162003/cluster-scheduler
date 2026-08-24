"""Two scalers, two private constants, forty moves; one shared number, one.

The horizontal scaler alone sits at its 0.7 target and makes zero
moves. Add a vertical scaler steering by its own 1.2x headroom constant
and the pair make forty moves in twenty rounds without converging: the
shrink raises the ratio, the ratio adds a replica, the replica lowers
per-use, the vertical shrinks again, request 500 to 73 and replicas 4
to 24. The truce is not scoping or rate limits; it is arithmetic: the
vertical sizes the request so the ratio lands exactly on the
horizontal's target, and the oversized fleet settles in one move.
Controllers fight when they steer the same state by different
constants, and stop when they agree on the number.
"""

from __future__ import annotations

from fleet.trials.verdict import Verdict
from fleet.vertical import FightMeter


def run() -> Verdict:
    alone = FightMeter(request=500, replicas=4, total_load=1400.0)
    alone_moves = alone.rounds(20, "off")

    fight = FightMeter(request=500, replicas=4, total_load=1400.0)
    fight_moves = fight.rounds(20, "private")

    truce = FightMeter(request=2000, replicas=4, total_load=1400.0)
    truce_moves = truce.rounds(20, "truce")

    numbers = {
        "moves_horizontal_alone": alone_moves,
        "moves_private_constants": fight_moves,
        "end_request_private": fight.request,
        "end_replicas_private": fight.replicas,
        "moves_truce": truce_moves,
        "end_state_truce": (truce.request, truce.replicas),
    }
    holds = (
        alone_moves == 0
        and fight_moves == 40
        and fight.request == 73
        and fight.replicas == 24
        and truce_moves == 1
        and (truce.request, truce.replicas) == (500, 4)
    )
    return Verdict(
        trial="scalerfight",
        sentence=(
            "the horizontal scaler alone makes zero moves, the pair with "
            "private constants make forty and diverge to request 73 with "
            "24 replicas, and the truce that sizes to the shared target "
            "settles an oversized fleet in exactly one move"
        ),
        numbers=numbers,
        holds=holds,
    )
