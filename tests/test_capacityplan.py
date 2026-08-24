from __future__ import annotations

from fleet.capacityplan import _days_until, project, survives_n_plus_one
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def loaded_store() -> Store:
    store = Store()
    store.add_node(Node(name="big", capacity=Resources(cpu=4000, memory=8000)))
    store.add_node(Node(name="mid", capacity=Resources(cpu=2000, memory=4000)))
    store.add_node(Node(name="small", capacity=Resources(cpu=1000, memory=2000)))
    task = Task(spec=TaskSpec(name="t", needs=Resources(cpu=2000, memory=9000)))
    task.bound_to("big")
    store.add_task(task)
    return store


class TestDaysUntil:
    def test_already_full_is_day_zero(self):
        assert _days_until(100, 100, 0.1) == 0

    def test_no_growth_never_fills(self):
        assert _days_until(50, 100, 0.0) is None

    def test_compounding_crosses_when_it_crosses(self):
        assert _days_until(50, 100, 0.10) == 8

    def test_slow_growth_takes_longer(self):
        fast = _days_until(50, 100, 0.10)
        slow = _days_until(50, 100, 0.01)
        assert slow > fast


class TestProjection:
    def test_the_axes_are_projected_separately(self):
        cpu, memory = project(loaded_store(), cpu_rate=0.01, memory_rate=0.05)
        assert cpu.axis == "cpu" and memory.axis == "memory"
        assert memory.days_left < cpu.days_left

    def test_the_line_reads_like_a_sentence(self):
        cpu, _ = project(loaded_store(), cpu_rate=0.01, memory_rate=0.05)
        assert "cpu: 2000/7000" in cpu.line()
        assert "full day" in cpu.line()

    def test_a_flat_axis_says_never(self):
        cpu, _ = project(loaded_store(), cpu_rate=0.0, memory_rate=0.0)
        assert "never" in cpu.line()


class TestNPlusOne:
    def test_a_light_cluster_survives(self):
        store = loaded_store()
        store.get_task("t").spec = TaskSpec(
            name="t", needs=Resources(cpu=500, memory=500)
        )
        survives, why = survives_n_plus_one(store)
        assert survives and "big" in why

    def test_a_heavy_cluster_does_not_and_says_what_strands(self):
        survives, why = survives_n_plus_one(loaded_store())
        assert not survives
        assert "strands" in why and "memory" in why

    def test_an_empty_fleet_fails_plainly(self):
        assert survives_n_plus_one(Store()) == (False, "no nodes")
