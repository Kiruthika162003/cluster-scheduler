"""The release train: channels, waves, a canary verdict, and the yank.

Run with: python -m examples.releasetrain
"""

from __future__ import annotations

from fleet.channels import Channels
from fleet.roll.canary import Canary
from fleet.roll.waves import Delivery, standard


def main() -> int:
    channels = Channels()
    channels.release("v41", now=0)
    for now in range(1, 25):
        channels.tick(now)
    print(f"v41: rapid at 0, stable at 20 after soak, "
          f"stable now {channels.version_for('stable')}")

    channels.release("v42", now=30)
    watcher = Canary(traffic_share=0.10)
    while watcher.state == "watching":
        watcher.tick(2000, stable_error_rate=0.004, canary_error_rate=0.09)
    print(f"v42 canary verdict: {watcher.state}")
    if watcher.state == "rollback":
        channels.yank("v42", now=32)
        print(f"v42 yanked; promotion frozen: {channels.frozen}")
    for now in range(33, 60):
        channels.tick(now)
    print(f"stable held at {channels.version_for('stable')} through the freeze")

    channels.release("v43", now=60)
    print(f"v43 released; promotion unfrozen: {not channels.frozen}")
    delivery = Delivery(build="v43", waves=standard())
    while delivery.state == "rolling":
        delivery.tick(healthy=True)
    print(f"v43 delivery: {delivery.state} after waves {delivery.reached()}")
    for now in range(61, 61 + 25):
        channels.tick(now)
    print(f"channels close with stable {channels.version_for('stable')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
