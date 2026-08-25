from __future__ import annotations

import pytest

from fleet.errors import Unschedulable
from fleet.federation import Federator, Member
from fleet.objects import Node, Resources, Task, TaskSpec
from fleet.store import Store


def member(name: str, region: str, nodes: int, used: int = 0) -> Member:
    store = Store()
    for number in range(nodes):
        store.add_node(
            Node(name=f"{name}-n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    if used:
        task = Task(spec=TaskSpec(name=f"{name}-load", needs=Resources(cpu=used, memory=100)))
        task.bound_to(f"{name}-n0")
        store.add_task(task)
    return Member(name=name, region=region, store=store)


def federation() -> Federator:
    federator = Federator()
    federator.join(member("east", "us", nodes=2))
    federator.join(member("west", "us", nodes=3))
    federator.join(member("eu", "eu", nodes=2, used=500))
    return federator


class TestPlacement:
    def test_the_roomiest_cluster_wins(self):
        federator = federation()
        assert federator.place("web", cpu=500) == "west"

    def test_region_constraints_filter_first(self):
        federator = federation()
        assert federator.place("gdpr-app", cpu=500, region="eu") == "eu"

    def test_headroom_counts_existing_load(self):
        federator = Federator()
        federator.join(member("full", "us", nodes=1, used=900))
        federator.join(member("empty", "us", nodes=1))
        assert federator.place("web", cpu=500) == "empty"

    def test_an_impossible_ask_names_every_cluster(self):
        federator = federation()
        with pytest.raises(Unschedulable) as caught:
            federator.place("giant", cpu=50000)
        for name in ("east", "west", "eu"):
            assert name in str(caught.value)


class TestFailover:
    def test_failover_repicks_excluding_the_failed_home(self):
        federator = federation()
        federator.place("web", cpu=500)
        chosen = federator.fail_over("web", cpu=500)
        assert chosen != "west"
        assert "failed over from west" in federator.log[-1]

    def test_failover_honours_the_region_even_in_grief(self):
        federator = federation()
        federator.place("gdpr-app", cpu=500, region="eu")
        with pytest.raises(Unschedulable):
            federator.fail_over("gdpr-app", cpu=500, region="eu")

    def test_a_first_placement_through_failover_just_places(self):
        federator = federation()
        chosen = federator.fail_over("fresh", cpu=100)
        assert chosen == "west"
