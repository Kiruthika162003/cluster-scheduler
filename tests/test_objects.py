from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.objects import (
    Node,
    Resources,
    Taint,
    Task,
    TaskSpec,
    allocated,
    free,
    relabelled,
)


def spec(name: str = "t", cpu: int = 100, memory: int = 200, **kw) -> TaskSpec:
    return TaskSpec(name=name, needs=Resources(cpu=cpu, memory=memory), **kw)


class TestResources:
    def test_plus_and_minus_are_componentwise(self):
        a = Resources(cpu=100, memory=200)
        b = Resources(cpu=30, memory=50)
        assert a.plus(b) == Resources(cpu=130, memory=250)
        assert a.minus(b) == Resources(cpu=70, memory=150)

    def test_fits_requires_both_axes(self):
        small = Resources(cpu=10, memory=1000)
        big = Resources(cpu=100, memory=100)
        assert not small.fits_in(big)
        assert not big.fits_in(small)
        assert small.fits_in(Resources(cpu=10, memory=1000))

    def test_negative_resources_are_refused(self):
        with pytest.raises(Invalid):
            Resources(cpu=-1, memory=0)

    def test_none_is_the_identity(self):
        a = Resources(cpu=5, memory=7)
        assert a.plus(Resources.none()) == a


class TestSpecs:
    def test_a_task_needs_a_name(self):
        with pytest.raises(Invalid):
            TaskSpec(name="", needs=Resources.none())

    def test_labels_read_back_as_a_map(self):
        made = spec(labels=(("app", "web"), ("tier", "front")))
        assert made.label_map() == {"app": "web", "tier": "front"}

    def test_an_unknown_taint_effect_is_refused(self):
        with pytest.raises(Invalid):
            Taint(key="gpu", effect="Sometimes")

    def test_relabelled_replaces_without_mutating(self):
        original = spec(priority=1)
        changed = relabelled(original, priority=9)
        assert original.priority == 1 and changed.priority == 9


class TestTaskAndNode:
    def test_binding_sets_phase_and_node(self):
        task = Task(spec=spec())
        task.bound_to("n1")
        assert task.phase == "Bound" and task.node == "n1"

    def test_only_bound_and_running_are_active(self):
        task = Task(spec=spec())
        assert not task.is_active()
        task.bound_to("n1")
        assert task.is_active()
        task.phase = "Failed"
        assert not task.is_active()

    def test_a_node_needs_a_name(self):
        with pytest.raises(Invalid):
            Node(name="", capacity=Resources.none())

    def test_allocated_sums_only_this_nodes_active_tasks(self):
        node = Node(name="n1", capacity=Resources(cpu=1000, memory=1000))
        here = Task(spec=spec("a", 100, 100))
        here.bound_to("n1")
        elsewhere = Task(spec=spec("b", 100, 100))
        elsewhere.bound_to("n2")
        finished = Task(spec=spec("c", 100, 100))
        finished.bound_to("n1")
        finished.phase = "Succeeded"
        used = allocated(node, [here, elsewhere, finished])
        assert used == Resources(cpu=100, memory=100)

    def test_free_is_capacity_minus_allocated(self):
        node = Node(name="n1", capacity=Resources(cpu=1000, memory=1000))
        task = Task(spec=spec("a", 300, 400))
        task.bound_to("n1")
        assert free(node, [task]) == Resources(cpu=700, memory=600)
