from __future__ import annotations

import pytest

from fleet.control.configs import ConfigBook, content_hash, serving_hashes
from fleet.control.deploy import Deployer, DeploySpec
from fleet.errors import NotFound
from fleet.objects import Resources, TaskSpec
from fleet.store import Store


def template() -> TaskSpec:
    return TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100))


class TestHashing:
    def test_the_hash_is_content_not_order(self):
        assert content_hash({"a": "1", "b": "2"}) == content_hash({"b": "2", "a": "1"})

    def test_any_value_change_moves_the_hash(self):
        assert content_hash({"a": "1"}) != content_hash({"a": "2"})

    def test_key_and_value_are_not_confusable(self):
        assert content_hash({"ab": "c"}) != content_hash({"a": "bc"})


class TestBook:
    def test_put_returns_the_hash(self):
        book = ConfigBook()
        told = book.put("c", {"k": "v"})
        assert told == book.hash_of("c")

    def test_editing_counts(self):
        book = ConfigBook()
        book.put("c", {"k": "v"})
        book.put("c", {"k": "w"})
        assert book.edits == 1

    def test_a_missing_config_is_not_found(self):
        with pytest.raises(NotFound):
            ConfigBook().get("ghost")

    def test_get_returns_a_copy(self):
        book = ConfigBook()
        book.put("c", {"k": "v"})
        held = book.get("c")
        held["k"] = "tampered"
        assert book.get("c") == {"k": "v"}


class TestStamping:
    def test_the_stamp_lands_on_the_template(self):
        book = ConfigBook()
        book.put("app", {"k": "v"})
        stamped = book.stamped_template(template(), "app")
        assert stamped.label_map()["config-app"] == book.hash_of("app")

    def test_an_edit_without_restamp_is_a_ghost(self):
        book = ConfigBook()
        old_hash = book.put("app", {"timeout": "5"})
        store = Store()
        deployer = Deployer()
        spec = book.stamped_deploy(
            DeploySpec(name="web", replicas=2, template=template()), "app"
        )
        deployer.reconcile(store, spec)
        book.put("app", {"timeout": "30"})
        assert serving_hashes(store, "web", "app") == {old_hash}

    def test_a_restamp_changes_the_template(self):
        book = ConfigBook()
        book.put("app", {"timeout": "5"})
        before = book.stamped_deploy(
            DeploySpec(name="web", replicas=2, template=template()), "app"
        )
        book.put("app", {"timeout": "30"})
        after = book.stamped_deploy(
            DeploySpec(name="web", replicas=2, template=template()), "app"
        )
        assert before.template != after.template

    def test_unstamped_fleets_report_unstamped(self):
        store = Store()
        deployer = Deployer()
        deployer.reconcile(
            store, DeploySpec(name="web", replicas=1, template=template())
        )
        assert serving_hashes(store, "web", "app") == {"unstamped"}
