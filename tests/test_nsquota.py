from __future__ import annotations

import pytest

from fleet.control.nsquota import Admission, NamespaceQuota
from fleet.errors import Invalid
from fleet.objects import Resources, Task, TaskSpec
from fleet.store import Store


def task(name: str, cpu: int = 100, namespace: str = "team-a") -> Task:
    return Task(
        spec=TaskSpec(
            name=name,
            needs=Resources(cpu=cpu, memory=cpu),
            namespace=namespace,
        )
    )


def admission() -> Admission:
    return Admission(
        quotas={
            "team-a": NamespaceQuota(
                namespace="team-a",
                max_tasks=3,
                max_requests=Resources(cpu=500, memory=500),
            )
        }
    )


class TestUsage:
    def test_usage_counts_only_the_namespace(self):
        store = Store()
        store.add_task(task("a"))
        store.add_task(task("other", namespace="team-b"))
        count, total = admission().usage(store, "team-a")
        assert count == 1 and total.cpu == 100

    def test_finished_tasks_refund_their_charge(self):
        store = Store()
        done = task("a")
        done.phase = "Succeeded"
        store.add_task(done)
        count, total = admission().usage(store, "team-a")
        assert count == 0 and total == Resources.none()


class TestAdmission:
    def test_within_quota_admits(self):
        store = Store()
        gate = admission()
        gate.admit(store, task("a"))
        assert gate.admitted == 1 and "a" in store.tasks

    def test_the_count_cap_refuses_with_the_arithmetic(self):
        store = Store()
        gate = admission()
        for number in range(3):
            gate.admit(store, task(f"t{number}"))
        with pytest.raises(Invalid) as caught:
            gate.admit(store, task("t3"))
        assert "3 of 3 tasks" in str(caught.value)
        assert gate.refused == 1

    def test_the_resource_cap_refuses_with_both_sides(self):
        store = Store()
        gate = admission()
        gate.admit(store, task("fat", cpu=400))
        with pytest.raises(Invalid) as caught:
            gate.admit(store, task("more", cpu=200))
        assert "600m" in str(caught.value) and "500m" in str(caught.value)

    def test_a_refused_task_is_not_added(self):
        store = Store()
        gate = admission()
        gate.admit(store, task("fat", cpu=500))
        with pytest.raises(Invalid):
            gate.admit(store, task("more", cpu=100))
        assert "more" not in store.tasks

    def test_unquotaed_namespaces_pass_free(self):
        store = Store()
        gate = admission()
        for number in range(10):
            gate.admit(store, task(f"b{number}", namespace="team-b"))
        assert gate.admitted == 10

    def test_deletion_makes_room_again(self):
        store = Store()
        gate = admission()
        for number in range(3):
            gate.admit(store, task(f"t{number}"))
        store.remove_task("t0")
        gate.admit(store, task("t3"))
        assert gate.admitted == 4
