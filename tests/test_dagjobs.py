from __future__ import annotations

from fleet.control.dagjobs import DagRun
from fleet.depends import DependencyGraph


def pipeline() -> DependencyGraph:
    graph = DependencyGraph()
    graph.declare("transform", "extract")
    graph.declare("load", "transform")
    graph.declare("report", "load")
    graph.declare("audit", "extract")
    return graph


class TestLaunching:
    def test_the_roots_launch_first(self):
        run = DagRun(graph=pipeline())
        assert run.launch_ready() == ["extract"]

    def test_parallel_branches_launch_together(self):
        run = DagRun(graph=pipeline())
        run.launch_ready()
        run.finish("extract", "succeeded")
        assert run.launch_ready() == ["audit", "transform"]

    def test_nothing_launches_twice(self):
        run = DagRun(graph=pipeline())
        run.launch_ready()
        assert run.launch_ready() == []


class TestEnds:
    def drive(self, run: DagRun, failures: set[str]) -> str:
        for _ in range(10):
            for job in run.launch_ready():
                run.finish(
                    job, "failed" if job in failures else "succeeded"
                )
            if run.state() != "running":
                break
        return run.state()

    def test_a_clean_pipeline_ends_done(self):
        run = DagRun(graph=pipeline())
        assert self.drive(run, failures=set()) == "done"
        assert run.launched == ["extract", "audit", "transform", "load", "report"]

    def test_a_failure_skips_downstream_and_runs_the_rest(self):
        run = DagRun(graph=pipeline())
        assert self.drive(run, failures={"transform"}) == "failed"
        assert "audit" in run.succeeded
        assert run.skipped == {
            "load": "transform",
            "report": "transform",
        }

    def test_the_skip_names_the_original_corpse_not_the_neighbour(self):
        run = DagRun(graph=pipeline())
        self.drive(run, failures={"transform"})
        assert run.skipped["report"] == "transform"

    def test_the_report_reads_the_whole_story(self):
        run = DagRun(graph=pipeline())
        self.drive(run, failures={"transform"})
        lines = run.report()
        assert any("failed: transform" in line for line in lines)
        assert any("skipped report: downstream of transform" in line for line in lines)
