from __future__ import annotations

from fleet.control.deploy import Deployer, DeploySpec
from fleet.drift import Detector
from fleet.objects import Resources, TaskSpec
from fleet.store import Store


def web(replicas: int = 3) -> DeploySpec:
    return DeploySpec(
        name="web",
        replicas=replicas,
        template=TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100)),
    )


def applied_store() -> tuple[Store, Deployer]:
    store = Store()
    deployer = Deployer()
    deployer.reconcile(store, web())
    return store, deployer


class TestSurvey:
    def test_a_faithful_cluster_reports_no_drift(self):
        store, _ = applied_store()
        assert Detector().survey(store, [web()]) == []

    def test_a_2am_scale_down_is_a_sentence(self):
        store, _ = applied_store()
        store.remove_task("web-2")
        drifts = Detector().survey(store, [web()])
        assert [d.sentence() for d in drifts] == [
            "web: replicas applied 3, observed 2"
        ]

    def test_a_2am_scale_up_is_also_drift(self):
        store, deployer = applied_store()
        deployer.reconcile(store, web(replicas=5))
        drifts = Detector().survey(store, [web(replicas=3)])
        assert drifts[0].observed == 5


class TestCorrection:
    def test_the_robot_puts_it_back(self):
        store, deployer = applied_store()
        store.remove_task("web-2")
        detector = Detector()
        corrected, respected = detector.correct(store, [web()], deployer)
        assert len(corrected) == 1 and respected == []
        assert len(store.tasks) == 3
        assert detector.corrections == 1

    def test_a_paused_deployment_is_reported_and_left_alone(self):
        store, deployer = applied_store()
        store.remove_task("web-2")
        detector = Detector()
        detector.pause("web")
        corrected, respected = detector.correct(store, [web()], deployer)
        assert corrected == [] and len(respected) == 1
        assert len(store.tasks) == 2
        assert detector.respected_pauses == 1

    def test_resume_reenables_the_robot(self):
        store, deployer = applied_store()
        store.remove_task("web-2")
        detector = Detector()
        detector.pause("web")
        detector.correct(store, [web()], deployer)
        detector.resume("web")
        detector.correct(store, [web()], deployer)
        assert len(store.tasks) == 3

    def test_correction_is_idempotent(self):
        store, deployer = applied_store()
        store.remove_task("web-2")
        detector = Detector()
        detector.correct(store, [web()], deployer)
        corrected, _ = detector.correct(store, [web()], deployer)
        assert corrected == []
