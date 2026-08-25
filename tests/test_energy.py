from __future__ import annotations

import pytest

from fleet.energy import (
    IDLE_WATTS,
    BatchShifter,
    CarbonCalendar,
    CarbonWindow,
    consolidation_savings,
    fleet_watts,
    node_watts,
)
from fleet.errors import Invalid
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def cluster(count: int = 2) -> Store:
    store = Store()
    for number in range(count):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    return store


def place(store: Store, name: str, node: str, cpu: int) -> None:
    task = Task(spec=TaskSpec(name=name, needs=Resources(cpu=cpu, memory=cpu)))
    task.bound_to(node)
    store.add_task(task)


class TestWatts:
    def test_an_idle_node_burns_its_floor(self):
        store = cluster(1)
        assert node_watts(store.get_node("n0"), []) == IDLE_WATTS

    def test_work_adds_the_slope(self):
        store = cluster(1)
        place(store, "t", "n0", 500)
        assert node_watts(store.get_node("n0"), store.active_tasks()) == 200

    def test_packing_saves_nothing_while_the_empty_node_is_on(self):
        spread = cluster(2)
        place(spread, "a", "n0", 500)
        place(spread, "b", "n1", 500)
        packed = cluster(2)
        place(packed, "a", "n0", 500)
        place(packed, "b", "n0", 500)
        assert fleet_watts(spread) - fleet_watts(packed) == 0.0
        assert fleet_watts(spread) == 400.0

    def test_the_saving_is_the_powered_down_floor(self):
        store = cluster(2)
        place(store, "a", "n0", 500)
        place(store, "b", "n1", 500)
        assert consolidation_savings(store) == IDLE_WATTS


class TestCalendar:
    def calendar(self) -> CarbonCalendar:
        cal = CarbonCalendar()
        cal.add(CarbonWindow(starts=18, ends=22, grams_per_watt=3.0))
        cal.add(CarbonWindow(starts=2, ends=6, grams_per_watt=0.2))
        return cal

    def test_the_peak_and_the_valley_read_back(self):
        cal = self.calendar()
        assert cal.intensity(19) == 3.0
        assert cal.intensity(3) == 0.2
        assert cal.intensity(12) == 1.0

    def test_a_flat_window_is_refused(self):
        with pytest.raises(Invalid):
            self.calendar().add(
                CarbonWindow(starts=5, ends=5, grams_per_watt=1.0)
            )

    def test_greenest_finds_the_valley(self):
        assert self.calendar().greenest(0, 24, span=4) == 2

    def test_a_span_wider_than_the_range_is_refused(self):
        with pytest.raises(Invalid):
            self.calendar().greenest(0, 3, span=4)


class TestShifter:
    def test_the_shift_reports_grams_saved(self):
        cal = CarbonCalendar()
        cal.add(CarbonWindow(starts=18, ends=22, grams_per_watt=3.0))
        cal.add(CarbonWindow(starts=2, ends=6, grams_per_watt=0.2))
        shifter = BatchShifter(calendar=cal)
        start, saved = shifter.place(
            "nightly-etl", watts=200, arrival=18, deadline=30, span=4
        )
        assert start == 22
        assert saved == 1600.0
        assert "nightly-etl: [18 -> 22], 1600.0g saved" in shifter.statement()

    def test_running_now_when_now_is_green_saves_nothing(self):
        cal = CarbonCalendar()
        shifter = BatchShifter(calendar=cal)
        start, saved = shifter.place(
            "job", watts=100, arrival=0, deadline=10, span=2
        )
        assert start == 0
        assert saved == 0.0
