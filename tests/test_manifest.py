from __future__ import annotations

import pytest

from fleet.control.deploy import Deployer
from fleet.errors import Invalid
from fleet.manifest import Applier, Manifest, parse
from fleet.store import Store


def data(replicas: int = 2) -> dict:
    return {
        "deploys": [
            {
                "name": "web",
                "replicas": replicas,
                "cpu": 200,
                "labels": {"app": "web"},
            }
        ],
        "quotas": [{"namespace": "team-a", "max_tasks": 5}],
        "budgets": [
            {
                "name": "floor",
                "selector_key": "app",
                "selector_value": "web",
                "min_available": 1,
            }
        ],
    }


class TestParse:
    def test_a_full_manifest_parses(self):
        manifest = parse(data())
        assert manifest.deploys[0].name == "web"
        assert manifest.quotas[0].max_tasks == 5
        assert manifest.budgets[0].min_available == 1

    def test_unknown_deploy_keys_are_refused(self):
        bad = data()
        bad["deploys"][0]["replicsa"] = 3
        with pytest.raises(Invalid) as caught:
            parse(bad)
        assert "replicsa" in str(caught.value)

    def test_unknown_sections_are_refused(self):
        with pytest.raises(Invalid):
            parse({"deploy": []})

    def test_a_deploy_needs_name_and_replicas(self):
        with pytest.raises(Invalid):
            parse({"deploys": [{"name": "web"}]})

    def test_labels_land_on_the_template(self):
        manifest = parse(data())
        assert manifest.deploys[0].template.label_map()["app"] == "web"


class TestPlan:
    def test_the_first_plan_creates(self):
        applier = Applier()
        plan = applier.plan(parse(data()))
        assert plan.create == ["deploy/web"] and plan.empty() is False

    def test_a_replica_change_plans_a_change(self):
        applier = Applier()
        applier.apply(parse(data()), Store(), Deployer())
        plan = applier.plan(parse(data(replicas=5)))
        assert plan.change == ["deploy/web"]

    def test_a_removed_deploy_plans_a_delete(self):
        applier = Applier()
        applier.apply(parse(data()), Store(), Deployer())
        plan = applier.plan(Manifest())
        assert plan.delete == ["deploy/web"]

    def test_an_unchanged_manifest_plans_nothing(self):
        applier = Applier()
        applier.apply(parse(data()), Store(), Deployer())
        assert applier.plan(parse(data())).empty()

    def test_lines_read_verb_first(self):
        applier = Applier()
        assert applier.plan(parse(data())).lines() == "create deploy/web"
        assert Applier().plan(Manifest()).lines() == "nothing to do"


class TestApply:
    def test_apply_executes_the_creation(self):
        store = Store()
        Applier().apply(parse(data()), store, Deployer())
        assert sorted(store.tasks) == ["web-0", "web-1"]

    def test_apply_scales_on_change(self):
        store = Store()
        applier = Applier()
        deployer = Deployer()
        applier.apply(parse(data()), store, deployer)
        applier.apply(parse(data(replicas=1)), store, deployer)
        assert sorted(store.tasks) == ["web-0"]

    def test_apply_deletes_the_departed(self):
        store = Store()
        applier = Applier()
        deployer = Deployer()
        applier.apply(parse(data()), store, deployer)
        applier.apply(Manifest(), store, deployer)
        assert store.tasks == {}

    def test_plan_then_apply_agree(self):
        store = Store()
        applier = Applier()
        planned = applier.plan(parse(data()))
        applied = applier.apply(parse(data()), store, Deployer())
        assert planned.lines() == applied.lines()
