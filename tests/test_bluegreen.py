from __future__ import annotations

from fleet.objects import Resources, TaskSpec
from fleet.roll.bluegreen import BlueGreen
from fleet.store import Store


def template() -> TaskSpec:
    return TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100))


class TestBlueGreen:
    def test_blue_serves_first(self):
        store = Store()
        stage = BlueGreen(replicas=2)
        stage.deploy_blue(store, template())
        assert stage.serving == "blue"
        assert sorted(store.tasks) == ["blue-0", "blue-1"]

    def test_staging_green_doubles_the_fleet(self):
        store = Store()
        stage = BlueGreen(replicas=2)
        stage.deploy_blue(store, template())
        stage.stage_green(store, template())
        assert stage.peak_tasks == 4

    def test_cutover_flips_the_server(self):
        stage = BlueGreen(replicas=2)
        stage.cut_over()
        assert stage.serving == "green"
        stage.cut_over()
        assert stage.serving == "blue"

    def test_retire_removes_only_the_standby(self):
        store = Store()
        stage = BlueGreen(replicas=2)
        stage.deploy_blue(store, template())
        stage.stage_green(store, template())
        stage.cut_over()
        stage.retire_standby(store)
        assert sorted(store.tasks) == ["green-0", "green-1"]

    def test_rollback_while_warm_is_one_move(self):
        assert BlueGreen(replicas=2).rollback_ticks() == 1

    def test_the_log_tells_the_ceremony(self):
        store = Store()
        stage = BlueGreen(replicas=1)
        stage.deploy_blue(store, template())
        stage.stage_green(store, template())
        stage.cut_over()
        stage.retire_standby(store)
        assert stage.log == [
            "blue up, serving",
            "green staged beside blue",
            "cutover, serving green",
            "blue retired",
        ]
