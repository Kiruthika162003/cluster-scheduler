from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.objects import Resources, Task, TaskSpec
from fleet.overload import OverloadValve
from fleet.store import Store


def task(name: str, namespace: str = "default") -> Task:
    return Task(
        spec=TaskSpec(
            name=name, needs=Resources(cpu=1, memory=1), namespace=namespace
        )
    )


class TestTheValve:
    def test_under_the_caps_everything_enters(self):
        valve = OverloadValve(max_objects=10, max_tasks_per_namespace=5)
        store = Store()
        for number in range(5):
            valve.admit_task(store, task(f"t{number}"))
        assert len(store.tasks) == 5

    def test_the_object_cap_refuses_with_arithmetic(self):
        valve = OverloadValve(max_objects=3, max_tasks_per_namespace=10)
        store = Store()
        for number in range(3):
            valve.admit_task(store, task(f"t{number}"))
        with pytest.raises(Invalid) as caught:
            valve.admit_task(store, task("t3"))
        assert "3 objects" in str(caught.value)
        assert "closes at 3" in str(caught.value)

    def test_the_namespace_cap_is_per_namespace(self):
        valve = OverloadValve(max_objects=100, max_tasks_per_namespace=2)
        store = Store()
        valve.admit_task(store, task("a0", "runaway"))
        valve.admit_task(store, task("a1", "runaway"))
        with pytest.raises(Invalid):
            valve.admit_task(store, task("a2", "runaway"))
        valve.admit_task(store, task("b0", "innocent"))

    def test_deletes_are_never_gated(self):
        valve = OverloadValve(max_objects=2, max_tasks_per_namespace=2)
        store = Store()
        valve.admit_task(store, task("a"))
        valve.admit_task(store, task("b"))
        store.remove_task("a")
        valve.admit_task(store, task("c"))
        assert sorted(store.tasks) == ["b", "c"]


class TestPressure:
    def test_the_gauge_reads_in_three_bands(self):
        valve = OverloadValve(max_objects=10, max_tasks_per_namespace=10)
        store = Store()
        assert valve.pressure(store).startswith("calm")
        for number in range(8):
            valve.admit_task(store, task(f"t{number}"))
        assert valve.pressure(store).startswith("warming")
        valve.admit_task(store, task("t8"))
        assert valve.pressure(store).startswith("NEAR THE VALVE")
