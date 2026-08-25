from __future__ import annotations

from fleet.control.deploy import DeploySpec
from fleet.objects import Resources, TaskSpec
from fleet.specdiff import deploy_diff, describe, task_spec_diff


def spec(cpu: int = 200, labels: tuple = (), priority: int = 0) -> TaskSpec:
    return TaskSpec(
        name="tpl",
        needs=Resources(cpu=cpu, memory=cpu),
        labels=labels,
        priority=priority,
    )


def deploy(replicas: int = 3, **kw) -> DeploySpec:
    return DeploySpec(name="web", replicas=replicas, template=spec(**kw))


class TestTaskSpecDiff:
    def test_changed_numbers_read_from_to(self):
        told = task_spec_diff(spec(cpu=200), spec(cpu=400))
        assert told == ["cpu 200m to 400m", "memory 200Mi to 400Mi"]

    def test_unchanged_fields_say_nothing(self):
        assert task_spec_diff(spec(), spec()) == []

    def test_label_lifecycle_reads_as_sentences(self):
        told = task_spec_diff(
            spec(labels=(("old", "x"), ("stay", "same"))),
            spec(labels=(("new", "y"), ("stay", "same"))),
        )
        assert told == [
            "label new added as y",
            "label old removed, was x",
        ]

    def test_a_changed_label_names_both_values(self):
        told = task_spec_diff(
            spec(labels=(("tier", "canary"),)),
            spec(labels=(("tier", "stable"),)),
        )
        assert told == ["label tier canary to stable"]


class TestDeployDiff:
    def test_the_deploy_name_prefixes_every_line(self):
        told = deploy_diff(deploy(replicas=3), deploy(replicas=5, cpu=400))
        assert told == [
            "web: replicas 3 to 5",
            "web: cpu 200m to 400m",
            "web: memory 200Mi to 400Mi",
        ]

    def test_the_diff_is_stable(self):
        one = deploy_diff(deploy(), deploy(replicas=9, priority=5))
        two = deploy_diff(deploy(), deploy(replicas=9, priority=5))
        assert one == two


class TestDescribe:
    def test_creation_and_deletion_read_whole(self):
        assert describe(None, deploy()) == ["web: created with 3 replicas"]
        assert describe(deploy(), None) == ["web: deleted, had 3 replicas"]

    def test_a_no_op_says_so(self):
        assert describe(deploy(), deploy()) == ["web: no changes"]
