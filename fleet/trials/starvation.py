"""Starvation measured, then aged away: the counter becomes the cure.

One 300m slot receives a steady stream of priority 5 tasks, one new
arrival per pass, each holding the slot for a pass. A priority 1 task
waits behind them: without aging it has waited 60 passes when the trial
stops counting, and it would wait forever, since a fresh rival outranks
it every single pass. With aging, one effective priority point per ten
passes waited, the old task reaches effective priority 5 at pass 39 and
takes the slot on the tie, because ties break by name and p sorts ahead
of r. The overtake the guess predicted for pass 50 never needed to
happen; drawing level was enough. The starvation counter and the cure
are the same number read in two directions.
"""

from __future__ import annotations

from fleet.sched.queue import SchedulingQueue
from fleet.trials.verdict import Verdict


def _stream(queue: SchedulingQueue, passes: int) -> int | None:
    """One slot per pass; returns the pass when 'patient' wins it, if ever."""
    queue.offer("patient", 1)
    for now in range(passes):
        queue.offer(f"rival-{now:03d}", 5)
        ready = queue.ready(now)
        winner = ready[0]
        queue.forget(winner)
        if winner == "patient":
            return now
    return None


def run() -> Verdict:
    hungry = SchedulingQueue()
    starved_at = _stream(hungry, passes=60)
    waited = hungry.waiting["patient"].passes_waited if "patient" in hungry.waiting else 0

    aged = SchedulingQueue(aging_every=10)
    landed_at = _stream(aged, passes=60)

    numbers = {
        "landed_without_aging": starved_at,
        "passes_waited_at_cutoff": waited,
        "landed_with_aging": landed_at,
        "aging_every": 10,
    }
    holds = starved_at is None and waited == 60 and landed_at == 39
    return Verdict(
        trial="starvation",
        sentence=(
            "the priority 1 task never lands in 60 passes of fresh "
            "priority 5 rivals; with one aged point per ten passes waited "
            "it draws level at pass 39 and wins on the name tie, and the "
            "starvation counter is the cure read backwards"
        ),
        numbers=numbers,
        holds=holds,
    )
