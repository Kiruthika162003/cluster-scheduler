"""The weighted dealer against a one-task consumer: the restart inverted it.

The fair queue's original dealer re-dealt each band from scratch on
every call, which was fine for the engine that consumes the whole list
and silently catastrophic for a consumer taking one task per pass: the
deal always restarted with the alphabetically first lane, so a 2:1
weighting for search served every ads task first, weights inverted by
the restart. The deficit credits fix carries balances across calls and
inside each deal, and both consumption patterns now read ass ass ass,
one ads then two search, exactly the stated ratio. Fairness is a
property of the stream only if the stream survives the consumer.
"""

from __future__ import annotations

from fleet.sched.queue import SchedulingQueue
from fleet.trials.verdict import Verdict


def _one_at_a_time() -> str:
    queue = SchedulingQueue(namespace_weights={"search": 2, "ads": 1})
    for number in range(8):
        queue.offer(f"s{number}", 100, namespace="search")
        queue.offer(f"a{number}", 100, namespace="ads")
    served = []
    for now in range(12):
        winner = queue.ready(now)[0]
        served.append(winner[0])
        queue.forget(winner)
    return "".join(served)


def _batch_head() -> str:
    queue = SchedulingQueue(namespace_weights={"search": 2, "ads": 1})
    for number in range(10):
        queue.offer(f"s{number}", 100, namespace="search")
        queue.offer(f"a{number}", 100, namespace="ads")
    return "".join(name[0] for name in queue.ready(0)[:9])


def run() -> Verdict:
    stream = _one_at_a_time()
    head = _batch_head()
    numbers = {
        "one_at_a_time": stream,
        "batch_head": head,
        "search_share_stream": stream.count("s") / len(stream),
    }
    holds = (
        stream == "assassassass"
        and head == "assassass"
        and abs(numbers["search_share_stream"] - 2 / 3) < 0.01
    )
    return Verdict(
        trial="dealrestart",
        sentence=(
            "the re-dealt band served every ads task first under a 2:1 "
            "search weighting because the deal restarted at the alphabet "
            "each pass; deficit credits carry across calls and both "
            "consumption patterns now read one ads then two search, the "
            "stated ratio surviving the consumer"
        ),
        numbers=numbers,
        holds=holds,
    )
