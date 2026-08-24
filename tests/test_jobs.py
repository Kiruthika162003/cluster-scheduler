from __future__ import annotations

from fleet.control.jobs import JobKeeper, JobSpec
from fleet.objects import Resources, TaskSpec
from fleet.store import Store


def spec(**kw) -> JobSpec:
    kw.setdefault("name", "crunch")
    kw.setdefault("completions", 3)
    kw.setdefault("parallelism", 2)
    kw.setdefault(
        "template", TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100))
    )
    return JobSpec(**kw)


def finish_all(store: Store, outcome: str = "Succeeded") -> None:
    for task in list(store.tasks.values()):
        if task.phase == "Pending":
            task.phase = outcome


class TestLaunching:
    def test_parallelism_caps_the_first_wave(self):
        store = Store()
        keeper = JobKeeper()
        assert keeper.reconcile(store, spec()) == "running"
        assert len(store.tasks) == 2

    def test_children_carry_job_and_index_labels(self):
        store = Store()
        JobKeeper().reconcile(store, spec())
        held = store.get_task("crunch-i0-a0")
        assert held.spec.label_map()["job"] == "crunch"
        assert held.spec.label_map()["index"] == "0"

    def test_completions_drain_wave_by_wave(self):
        store = Store()
        keeper = JobKeeper()
        keeper.reconcile(store, spec())
        finish_all(store)
        assert keeper.reconcile(store, spec()) == "running"
        finish_all(store)
        assert keeper.reconcile(store, spec()) == "done"
        assert keeper.launched == 3


class TestRetries:
    def test_a_failed_index_retries_under_a_new_attempt(self):
        store = Store()
        keeper = JobKeeper()
        keeper.reconcile(store, spec(completions=1, parallelism=1))
        finish_all(store, outcome="Failed")
        keeper.reconcile(store, spec(completions=1, parallelism=1))
        assert "crunch-i0-a1" in store.tasks
        assert keeper.retried == 1

    def test_an_exhausted_index_kills_the_job(self):
        store = Store()
        keeper = JobKeeper()
        job = spec(completions=1, parallelism=1, retries_per_index=0)
        keeper.reconcile(store, job)
        finish_all(store, outcome="Failed")
        keeper.reconcile(store, job)
        assert keeper.reconcile(store, job) == "dead"

    def test_success_after_retry_still_counts(self):
        store = Store()
        keeper = JobKeeper()
        job = spec(completions=1, parallelism=1)
        keeper.reconcile(store, job)
        finish_all(store, outcome="Failed")
        keeper.reconcile(store, job)
        finish_all(store, outcome="Succeeded")
        assert keeper.reconcile(store, job) == "done"


class TestBookkeeping:
    def test_finished_children_are_cleaned_up(self):
        store = Store()
        keeper = JobKeeper()
        job = spec(completions=2, parallelism=2)
        keeper.reconcile(store, job)
        finish_all(store)
        keeper.reconcile(store, job)
        assert store.tasks == {}

    def test_a_done_job_stays_done(self):
        store = Store()
        keeper = JobKeeper()
        job = spec(completions=1, parallelism=1)
        keeper.reconcile(store, job)
        finish_all(store)
        assert keeper.reconcile(store, job) == "done"
        assert keeper.reconcile(store, job) == "done"
        assert keeper.launched == 1
