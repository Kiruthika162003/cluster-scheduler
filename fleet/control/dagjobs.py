"""DAG jobs: the pipeline runs everything it can, as soon as it can.

A workflow names jobs and the edges between them. The runner launches
every job whose needs have succeeded, in parallel where the graph
allows, and settles into exactly one of three ends: done when every
job succeeded, failed when a job died and everything not depending on
it still ran to its own end, or never wedged, because a pipeline that
stops running ready work while it waits for a human is spending
compute on drama. Failure is inherited: a job downstream of a corpse
is skipped with the corpse named.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.depends import DependencyGraph


@dataclass
class DagRun:
    graph: DependencyGraph
    succeeded: set[str] = field(default_factory=set)
    failed: set[str] = field(default_factory=set)
    skipped: dict[str, str] = field(default_factory=dict)
    running: set[str] = field(default_factory=set)
    launched: list[str] = field(default_factory=list)

    def _doomed_by(self, job: str) -> str | None:
        walk = list(self.graph.needs.get(job, set()))
        seen = set()
        while walk:
            current = walk.pop()
            if current in self.failed:
                return current
            if current in self.skipped:
                return self.skipped[current]
            if current in seen:
                continue
            seen.add(current)
            walk.extend(self.graph.needs.get(current, set()))
        return None

    def launchable(self) -> list[str]:
        ready = []
        for job in sorted(self.graph.needs):
            if (
                job in self.succeeded
                or job in self.failed
                or job in self.skipped
                or job in self.running
            ):
                continue
            corpse = self._doomed_by(job)
            if corpse is not None:
                self.skipped[job] = corpse
                continue
            needs = self.graph.needs.get(job, set())
            if needs <= self.succeeded:
                ready.append(job)
        return ready

    def launch_ready(self) -> list[str]:
        ready = self.launchable()
        for job in ready:
            self.running.add(job)
            self.launched.append(job)
        return ready

    def finish(self, job: str, outcome: str) -> None:
        self.running.discard(job)
        if outcome == "succeeded":
            self.succeeded.add(job)
        else:
            self.failed.add(job)

    def state(self) -> str:
        self.launchable()
        total = set(self.graph.needs)
        settled = self.succeeded | self.failed | set(self.skipped)
        if self.running or settled != total:
            return "running"
        if self.failed:
            return "failed"
        return "done"

    def report(self) -> list[str]:
        lines = [f"succeeded: {', '.join(sorted(self.succeeded)) or 'none'}"]
        if self.failed:
            lines.append(f"failed: {', '.join(sorted(self.failed))}")
        for job, corpse in sorted(self.skipped.items()):
            lines.append(f"skipped {job}: downstream of {corpse}")
        return lines
