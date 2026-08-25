"""Three nights of the batch: cron fires, indexes crunch, flakes retry.

Run with: python -m examples.batchnight
"""

from __future__ import annotations

from dataclasses import replace

from fleet.control.cron import Cron, Schedule
from fleet.control.jobs import JobKeeper, JobSpec
from fleet.objects import Resources, TaskSpec
from fleet.store import Store


def base_job(name: str) -> JobSpec:
    return JobSpec(
        name=name,
        completions=6,
        parallelism=2,
        retries_per_index=2,
        template=TaskSpec(name="tpl", needs=Resources(cpu=200, memory=200)),
    )


def main() -> int:
    cron = Cron(
        schedules=[
            Schedule(
                name="rebuild",
                every=100,
                job=base_job("rebuild"),
                missed_policy="one-shot",
            )
        ]
    )
    store = Store()
    keeper = JobKeeper()
    flaky_indexes = {2, 4}
    runs: list[JobSpec] = []
    finished: set[str] = set()

    for now in range(300):
        for fired in cron.tick(now):
            run_name = f"rebuild-run{len(runs)}"
            runs.append(replace(base_job(run_name), name=run_name))
            del fired
        for spec in runs:
            if spec.name in finished:
                continue
            state = keeper.reconcile(store, spec)
            if state in ("done", "dead"):
                finished.add(spec.name)
                print(f"{spec.name} {state} at tick {now}")
        for task in list(store.tasks.values()):
            if task.phase != "Pending":
                continue
            index = int(task.spec.label_map()["index"])
            attempt = int(task.spec.name.rsplit("-a", 1)[1])
            task.phase = (
                "Failed" if index in flaky_indexes and attempt == 0 else "Succeeded"
            )

    print(f"nights run: {len(runs)}, all finished: {len(finished) == len(runs)}")
    print(
        f"launched {keeper.launched} tasks for "
        f"{len(runs) * 6} completions, retried {keeper.retried}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
