from __future__ import annotations

from fleet.objects import Resources, Task, TaskSpec
from fleet.store import Store
from fleet.tenancyreport import quota_map, rendered, standard_quota, survey


def task(name: str, namespace: str, cpu: int, phase: str = "Pending") -> Task:
    made = Task(
        spec=TaskSpec(
            name=name, needs=Resources(cpu=cpu, memory=cpu), namespace=namespace
        )
    )
    if phase == "Bound":
        made.bound_to("n0")
    else:
        made.phase = phase
    return made


def busy_store() -> Store:
    store = Store()
    store.add_task(task("a", "team-a", 300, phase="Bound"))
    store.add_task(task("b", "team-a", 200, phase="Pending"))
    store.add_task(task("c", "team-b", 100, phase="Bound"))
    store.add_task(task("done", "team-b", 900, phase="Succeeded"))
    return store


class TestSurvey:
    def test_rows_split_running_and_pending(self):
        rows = survey(busy_store(), {})
        by_name = {row.namespace: row for row in rows}
        assert by_name["team-a"].running == 1
        assert by_name["team-a"].pending == 1

    def test_finished_tasks_do_not_count(self):
        rows = survey(busy_store(), {})
        by_name = {row.namespace: row for row in rows}
        assert by_name["team-b"].cpu_used == 100

    def test_hoarding_is_pending_requests(self):
        rows = survey(busy_store(), {})
        by_name = {row.namespace: row for row in rows}
        assert by_name["team-a"].hoarded_cpu == 200
        assert by_name["team-b"].hoarded_cpu == 0

    def test_headroom_is_quota_minus_used(self):
        quotas = quota_map(standard_quota("team-a", cpu=600))
        rows = survey(busy_store(), quotas)
        by_name = {row.namespace: row for row in rows}
        assert by_name["team-a"].headroom == 100
        assert by_name["team-b"].headroom is None

    def test_a_quota_only_namespace_still_appears(self):
        quotas = quota_map(standard_quota("team-idle", cpu=500))
        rows = survey(Store(), quotas)
        assert rows[0].namespace == "team-idle" and rows[0].cpu_used == 0

    def test_strained_means_no_headroom(self):
        quotas = quota_map(standard_quota("team-a", cpu=500))
        rows = survey(busy_store(), quotas)
        by_name = {row.namespace: row for row in rows}
        assert by_name["team-a"].strained()


class TestRender:
    def test_the_page_marks_the_strained(self):
        quotas = quota_map(standard_quota("team-a", cpu=500))
        page = rendered(busy_store(), quotas)
        assert "STRAINED" in page
        assert "team-b" in page

    def test_quotaless_namespaces_show_dashes(self):
        page = rendered(busy_store(), {})
        assert "-" in page
