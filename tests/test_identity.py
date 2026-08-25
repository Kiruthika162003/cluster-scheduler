from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.identity import LIFETIME, mint, verify
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def placed_store() -> Store:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    task = Task(
        spec=TaskSpec(
            name="web-0",
            needs=Resources(cpu=100, memory=100),
            namespace="shop",
            labels=(("app", "web"),),
        )
    )
    task.bound_to("n0")
    store.add_task(task)
    return store


class TestMinting:
    def test_the_name_is_derived_from_placement(self):
        store = placed_store()
        document = mint(store, "web-0", now=0)
        assert document.name() == "shop/web@n0"

    def test_an_unplaced_task_gets_no_identity(self):
        store = placed_store()
        held = store.get_task("web-0")
        held.phase = "Pending"
        held.node = None
        with pytest.raises(Invalid):
            mint(store, "web-0", now=0)


class TestVerification:
    def test_a_fresh_document_verifies(self):
        store = placed_store()
        document = mint(store, "web-0", now=0)
        verified, why = verify(store, document, "web-0", now=5)
        assert verified and why == "verified as shop/web@n0"

    def test_expiry_ages_out_a_stolen_document(self):
        store = placed_store()
        document = mint(store, "web-0", now=0)
        verified, why = verify(store, document, "web-0", now=LIFETIME)
        assert not verified and "expired" in why

    def test_the_store_outranks_the_paper_on_placement(self):
        store = placed_store()
        document = mint(store, "web-0", now=0)
        held = store.get_task("web-0")
        generation = held.generation
        held.node = "n9"
        store.update_task(held, read_generation=generation)
        verified, why = verify(store, document, "web-0", now=5)
        assert not verified
        assert "document says n0, the store says n9" in why

    def test_a_dead_task_fails_before_expiry(self):
        store = placed_store()
        document = mint(store, "web-0", now=0)
        store.remove_task("web-0")
        verified, why = verify(store, document, "web-0", now=1)
        assert not verified and "no longer runs" in why
