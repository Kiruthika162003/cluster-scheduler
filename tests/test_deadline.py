from __future__ import annotations

import pytest

from fleet.sched.deadline import (
    BatchJob,
    jobs_late,
    lateness_table,
    max_lateness,
    run_order,
)

JOBS = [
    BatchJob("b", duration=10, deadline=30),
    BatchJob("a", duration=5, deadline=10),
]


class TestOrdering:
    def test_fifo_keeps_arrival(self):
        assert [job.name for job in run_order(JOBS, "fifo")] == ["b", "a"]

    def test_sjf_sorts_by_duration(self):
        assert [job.name for job in run_order(JOBS, "sjf")] == ["a", "b"]

    def test_edf_sorts_by_deadline(self):
        assert [job.name for job in run_order(JOBS, "edf")] == ["a", "b"]

    def test_unknown_policies_are_refused(self):
        with pytest.raises(ValueError):
            run_order(JOBS, "vibes")


class TestLateness:
    def test_the_table_is_finish_minus_deadline(self):
        table = lateness_table(JOBS, "edf")
        assert table == {"a": -5, "b": -15}

    def test_fifo_here_makes_a_late(self):
        table = lateness_table(JOBS, "fifo")
        assert table["a"] == 5

    def test_counters_agree_with_the_table(self):
        assert max_lateness(JOBS, "fifo") == 5
        assert jobs_late(JOBS, "fifo") == 1
        assert jobs_late(JOBS, "edf") == 0
