"""Address reuse against messages in flight: 73 misdeliveries or 20 denials.

Tenants hold an address four ticks, send a parting message as they
leave, and the message flies for three. With no cooldown the pool
reissues the address inside the flight window and 73 parting messages
land on strangers over eighty ticks. A cooldown of four, one tick past
the flight time, takes misdeliveries to zero and presents the bill as
20 denied allocations, the pool headroom spent keeping addresses cool.
Nothing was tuned away; the window moved the cost from correctness to
capacity, which is the only direction it can move.
"""

from __future__ import annotations

from fleet.allocator import Allocator, FlightModel
from fleet.trials.verdict import Verdict

HOLD = 4
FLIGHT = 3
POOL = 6
TICKS = 80


def _churn(cooldown: int) -> tuple[int, int, int]:
    allocator = Allocator(pool_size=POOL, cooldown=cooldown)
    flight = FlightModel(flight_time=FLIGHT)
    tenants: dict[str, int] = {}
    denied = 0
    for now in range(TICKS):
        name = f"tenant-{now}"
        address = allocator.allocate(name, now)
        if address is None:
            denied += 1
        else:
            tenants[name] = address
            flight.send(address, name, now)
        for held_name, held_address in list(tenants.items()):
            born = int(held_name.split("-")[1])
            if now - born >= HOLD:
                flight.send(held_address, held_name, now)
                allocator.release(held_address, now)
                del tenants[held_name]
        flight.deliver(allocator, now)
    return len(flight.misdelivered), flight.delivered, denied


def run() -> Verdict:
    hot_mis, hot_ok, hot_denied = _churn(cooldown=0)
    cool_mis, cool_ok, cool_denied = _churn(cooldown=FLIGHT + 1)

    numbers = {
        "misdelivered_no_cooldown": hot_mis,
        "delivered_no_cooldown": hot_ok,
        "denied_no_cooldown": hot_denied,
        "misdelivered_cooled": cool_mis,
        "delivered_cooled": cool_ok,
        "denied_cooled": cool_denied,
    }
    holds = (
        hot_mis == 73
        and hot_denied == 0
        and cool_mis == 0
        and cool_denied == 20
    )
    return Verdict(
        trial="staleaddress",
        sentence=(
            "immediate reuse hands 73 parting messages to strangers with "
            "zero denials; a cooldown one tick past the flight time takes "
            "misdeliveries to zero and bills 20 denials instead, moving "
            "the cost from correctness to capacity"
        ),
        numbers=numbers,
        holds=holds,
    )
