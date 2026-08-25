from __future__ import annotations

from fleet.control.budget import Budget, Guard
from fleet.control.health import BACKOFF_CAP, FORGIVE_AFTER, Keeper, Probe, StartupGate
from fleet.objects import Resources, Task, TaskSpec
from fleet.roll.rolling import Roller, Rollout
from fleet.store import Store


def template() -> TaskSpec:
    return TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100))


def seeded(roller: Roller, revision: int, count: int = 3) -> Store:
    store = Store()
    roll = Rollout(name="web", replicas=count, template=template(), revision=revision)
    for ordinal in range(count):
        task = Task(spec=roller._stamped(roll, ordinal))
        task.bound_to(f"n{ordinal}")
        task.phase = "Running"
        store.add_task(task)
    return store


def run_out(store: Store, roller: Roller, roll: Rollout, guard=None) -> list[str]:
    history = []
    for _ in range(30):
        what = roller.step(store, roll, guard)
        history.append(what)
        for task in store.tasks.values():
            if task.phase == "Pending":
                task.phase = "Running"
        if what in ("done", "stuck"):
            break
    return history


class TestRolling:
    def test_the_rollout_alternates_surge_and_retire(self):
        roller = Roller()
        store = seeded(roller, revision=1)
        new = Rollout(name="web", replicas=3, template=template(), revision=2)
        history = run_out(store, roller, new)
        assert history == [
            "surged", "retired", "surged", "retired", "surged", "retired", "done",
        ]

    def test_the_end_state_is_all_new_revision(self):
        roller = Roller()
        store = seeded(roller, revision=1)
        new = Rollout(name="web", replicas=3, template=template(), revision=2)
        run_out(store, roller, new)
        assert sorted(store.tasks) == ["web-r2-0", "web-r2-1", "web-r2-2"]

    def test_surge_never_exceeds_the_limit(self):
        roller = Roller()
        store = seeded(roller, revision=1)
        new = Rollout(
            name="web", replicas=3, template=template(), revision=2, max_surge=1
        )
        for _ in range(30):
            count = len(store.tasks)
            assert count <= 3 + 1
            if roller.step(store, new) == "done":
                break
            for task in store.tasks.values():
                if task.phase == "Pending":
                    task.phase = "Running"

    def test_an_unhealthy_new_revision_stops_the_rollout(self):
        roller = Roller()
        store = seeded(roller, revision=1)
        new = Rollout(name="web", replicas=3, template=template(), revision=2)
        first = roller.step(store, new)
        stuck = roller.step(store, new)
        assert first == "surged" and stuck == "stuck"
        survivors = [t for t in store.tasks.values() if "r1" in t.spec.name]
        assert len(survivors) == 3

    def test_a_budget_floor_can_stall_the_retire(self):
        roller = Roller()
        store = seeded(roller, revision=1)
        guard = Guard(
            budgets=[
                Budget(
                    name="floor",
                    selector_key="deploy",
                    selector_value="web",
                    min_available=4,
                )
            ]
        )
        new = Rollout(name="web", replicas=3, template=template(), revision=2)
        history = run_out(store, roller, new, guard)
        assert history[-1] == "stuck" and roller.halted == 1

    def test_a_finished_rollout_reports_done_forever(self):
        roller = Roller()
        store = seeded(roller, revision=2)
        roll = Rollout(name="web", replicas=3, template=template(), revision=2)
        assert roller.step(store, roll) == "done"
        assert roller.step(store, roll) == "done"


class TestKeeper:
    def flaky_store(self, failures: set[int]) -> tuple[Store, Keeper]:
        store = Store()
        task = Task(spec=TaskSpec(name="t", needs=Resources(cpu=1, memory=1)))
        task.bound_to("n0")
        store.add_task(task)
        keeper = Keeper(probes={"t": Probe(failing_attempts=frozenset(failures))})
        return store, keeper

    def test_a_clean_task_runs_on_the_first_tick(self):
        store, keeper = self.flaky_store(set())
        keeper.tick(store, 0)
        assert store.get_task("t").phase == "Running"

    def test_each_failure_doubles_the_wait(self):
        keeper = Keeper()
        assert [keeper.backoff_for(n) for n in (1, 2, 3, 4)] == [2, 4, 8, 16]

    def test_the_ladder_caps(self):
        keeper = Keeper()
        assert keeper.backoff_for(10) == BACKOFF_CAP

    def test_a_failing_probe_restarts_and_waits(self):
        store, keeper = self.flaky_store({0})
        keeper.tick(store, 0)
        assert store.get_task("t").restarts == 1
        keeper.tick(store, 1)
        assert store.get_task("t").phase == "Bound"
        keeper.tick(store, 2)
        assert store.get_task("t").phase == "Running"

    def test_sustained_health_forgives_the_restarts(self):
        store, keeper = self.flaky_store({0})
        for now in range(FORGIVE_AFTER + 5):
            keeper.tick(store, now)
        assert store.get_task("t").restarts == 0
        assert keeper.forgiven == 1

    def test_forgiveness_requires_the_full_quiet_run(self):
        store, keeper = self.flaky_store({0})
        for now in range(FORGIVE_AFTER):
            keeper.tick(store, now)
        assert store.get_task("t").restarts == 1


class TestStartupGate:
    def gated_store(self, failures: frozenset) -> tuple:
        store = Store()
        task = Task(spec=TaskSpec(name="t", needs=Resources(cpu=1, memory=1)))
        task.bound_to("n0")
        store.add_task(task)
        gate = StartupGate(budget=10)
        keeper = Keeper(
            probes={"t": Probe(failing_attempts=failures)}, startup_gate=gate
        )
        return store, keeper, gate

    def test_a_slow_starter_is_absorbed_not_restarted(self):
        store, keeper, gate = self.gated_store(frozenset(range(8)))
        for now in range(12):
            keeper.tick(store, now)
        assert store.get_task("t").phase == "Running"
        assert keeper.restarts == 0
        assert gate.absorbed["t"] == 8

    def test_a_never_starter_is_declared_broken(self):
        store, keeper, gate = self.gated_store(frozenset(range(100)))
        for now in range(15):
            keeper.tick(store, now)
        assert store.get_task("t").phase == "Failed"
        assert "t" in gate.broken
        assert keeper.restarts == 0

    def test_after_first_up_liveness_rules_again(self):
        store, keeper, gate = self.gated_store(frozenset())
        keeper.tick(store, 0)
        assert store.get_task("t").phase == "Running"
        assert "t" in gate.started
        held = store.get_task("t")
        generation = held.generation
        held.phase = "Bound"
        store.update_task(held, read_generation=generation)
        keeper.probes["t"] = Probe(failing_attempts=frozenset(range(100)))
        keeper.tick(store, 1)
        assert keeper.restarts == 1
        assert store.get_task("t").phase == "Bound"


class TestPauseResume:
    def test_a_paused_rollout_stands_perfectly_still(self):
        roller = Roller()
        store = seeded(roller, revision=1)
        fresh = Rollout(name="web", replicas=3, template=template(), revision=2)
        roller.step(store, fresh)
        count_before = len(store.tasks)
        roller.pause()
        for _ in range(5):
            assert roller.step(store, fresh) == "paused"
        assert len(store.tasks) == count_before

    def test_resume_continues_where_it_stood(self):
        roller = Roller()
        store = seeded(roller, revision=1)
        fresh = Rollout(name="web", replicas=3, template=template(), revision=2)
        roller.step(store, fresh)
        for task in store.tasks.values():
            if task.phase == "Pending":
                task.phase = "Running"
        roller.pause()
        roller.step(store, fresh)
        roller.resume()
        history = run_out(store, roller, fresh)
        assert history[-1] == "done"
        assert sorted(store.tasks) == ["web-r2-0", "web-r2-1", "web-r2-2"]

    def test_pausing_a_finished_rollout_reports_paused_not_done(self):
        roller = Roller()
        store = seeded(roller, revision=2)
        roll = Rollout(name="web", replicas=3, template=template(), revision=2)
        roller.pause()
        assert roller.step(store, roll) == "paused"
