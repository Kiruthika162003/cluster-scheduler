from __future__ import annotations

import pytest

from fleet.catalog import Catalog, CatalogEntry
from fleet.control.deploy import Deployer, DeploySpec
from fleet.errors import NotFound
from fleet.objects import Resources, TaskSpec
from fleet.store import Store


def web_entry() -> CatalogEntry:
    return CatalogEntry(
        deploy="web",
        team="storefront",
        channel="#storefront-alerts",
        escalation=("meera", "raj", "storefront-lead"),
    )


class TestOwnership:
    def test_the_owner_is_answerable(self):
        catalog = Catalog()
        catalog.register(web_entry())
        assert catalog.owner_of("web").team == "storefront"

    def test_an_unregistered_deploy_is_not_found(self):
        with pytest.raises(NotFound):
            Catalog().owner_of("mystery")

    def test_the_team_page_lists_a_teams_services(self):
        catalog = Catalog()
        catalog.register(web_entry())
        catalog.register(
            CatalogEntry(
                deploy="cart",
                team="storefront",
                channel="#storefront-alerts",
                escalation=("meera",),
            )
        )
        assert catalog.team_page("storefront") == ["cart", "web"]


class TestEscalation:
    def test_the_chain_walks_in_order(self):
        catalog = Catalog()
        catalog.register(web_entry())
        assert catalog.page_target("web", 0) == "meera"
        assert catalog.page_target("web", 2) == "storefront-lead"

    def test_an_exhausted_chain_belongs_to_everyone(self):
        catalog = Catalog()
        catalog.register(web_entry())
        assert catalog.page_target("web", 3) == "everyone: the chain is exhausted"


class TestGovernance:
    def test_unowned_running_deploys_are_named(self):
        store = Store()
        deployer = Deployer()
        for name in ("web", "shadow-service"):
            spec = DeploySpec(
                name=name,
                replicas=1,
                template=TaskSpec(name="tpl", needs=Resources(cpu=1, memory=1)),
            )
            deployer.reconcile(store, spec)
        for task in store.tasks.values():
            task.bound_to("n0")
        catalog = Catalog()
        catalog.register(web_entry())
        assert catalog.unowned_deploys(store) == ["shadow-service"]

    def test_a_fully_owned_fleet_lists_nothing(self):
        catalog = Catalog()
        catalog.register(web_entry())
        assert catalog.unowned_deploys(Store()) == []
