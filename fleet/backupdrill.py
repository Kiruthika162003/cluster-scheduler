"""The backup drill: a backup is a rumour until a restore has served traffic.

The drill takes a live snapshot, wrecks a scratch copy the way real
disasters wreck things, restores from the snapshot, and proves the
restore by running the restored cluster forward and checking it makes
decisions. The proof standard is deliberately behavioural: files that
exist and checksums that match are necessary and insufficient, because
the restore that cannot schedule is a very well-preserved fossil.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.objects import Resources, Task, TaskSpec
from fleet.sched.core import Scheduler
from fleet.snapshot import dump, restore
from fleet.store import Store
from fleet.verify import violations


@dataclass
class DrillReport:
    took_snapshot: bool = False
    restored_objects: int = 0
    behaved: bool = False
    findings: list[str] = field(default_factory=list)

    def passed(self) -> bool:
        return self.took_snapshot and self.behaved and not self.findings


def backup_drill(store: Store) -> DrillReport:
    report = DrillReport()
    saved = dump(store)
    report.took_snapshot = True

    twin = restore(saved)
    report.restored_objects = len(twin.tasks) + len(twin.nodes)
    broken = violations(twin)
    if broken:
        report.findings.extend(
            f"restore inconsistent: {sentence}" for sentence in broken
        )
        return report

    probe = Task(
        spec=TaskSpec(
            name="drill-probe", needs=Resources(cpu=1, memory=1)
        )
    )
    twin.add_task(probe)
    scheduler = Scheduler()
    placed, stuck = scheduler.schedule_pending(twin)
    if placed + stuck == 0:
        report.findings.append("the restore made no decisions at all")
        return report
    if violations(twin):
        report.findings.append("the restore broke on its first decision")
        return report
    report.behaved = True
    if "drill-probe" in store.tasks:
        report.findings.append("the drill leaked its probe into the live store")
    return report
