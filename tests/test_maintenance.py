from __future__ import annotations

from fleet.maintenance import Calendar, GatedRoller, Window
from fleet.objects import Resources, Task, TaskSpec
from fleet.roll.rolling import Roller, Rollout
from fleet.store import Store


def weekend() -> Calendar:
    calendar = Calendar()
    calendar.add(Window(start=100, end=150, reason="weekend"))
    return calendar


class TestCalendar:
    def test_open_ticks_allow(self):
        allowed, opens = weekend().may_change(50)
        assert allowed and opens == 50

    def test_frozen_ticks_refuse_with_the_opening(self):
        calendar = weekend()
        allowed, opens = calendar.may_change(120)
        assert not allowed and opens == 150
        assert calendar.refusals == 1

    def test_chained_windows_walk_to_the_gap(self):
        calendar = weekend()
        calendar.add(Window(start=150, end=200, reason="holiday"))
        _, opens = calendar.may_change(120)
        assert opens == 200

    def test_the_boundary_tick_is_open(self):
        assert weekend().may_change(150)[0]

    def test_frozen_at_names_the_window(self):
        assert weekend().frozen_at(120).reason == "weekend"
        assert weekend().frozen_at(99) is None


class TestGatedRoller:
    def test_the_gate_defers_to_the_calendar(self):
        roller = Roller()
        store = Store()
        template = TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100))
        seed = Rollout(name="web", replicas=1, template=template, revision=1)
        task = Task(spec=roller._stamped(seed, 0))
        task.bound_to("n0")
        task.phase = "Running"
        store.add_task(task)
        roll = Rollout(name="web", replicas=1, template=template, revision=2)
        gated = GatedRoller(calendar=weekend())
        assert gated.step(roller, store, roll, tick=120) == "frozen-until-150"
        assert gated.waited == 1
        assert gated.step(roller, store, roll, tick=150) == "surged"
