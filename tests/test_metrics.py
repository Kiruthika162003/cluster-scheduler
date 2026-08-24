from __future__ import annotations

import pytest

from fleet.control.deploy import DeploySpec
from fleet.errors import Invalid
from fleet.metrics import Registry, scrape
from fleet.objects import Resources, TaskSpec
from fleet.sim.cluster import Sim


class TestPrimitives:
    def test_counters_only_go_up(self):
        registry = Registry()
        counter = registry.counter("hits_total", "hits")
        counter.bump()
        counter.bump(3)
        assert counter.value == 4
        with pytest.raises(Invalid):
            counter.bump(-1)

    def test_gauges_follow_the_truth(self):
        registry = Registry()
        gauge = registry.gauge("depth", "queue depth")
        gauge.set(5)
        gauge.set(2)
        assert gauge.value == 2

    def test_a_name_cannot_change_kind(self):
        registry = Registry()
        registry.counter("thing", "a thing")
        with pytest.raises(Invalid):
            registry.gauge("thing", "the same thing")

    def test_reregistering_returns_the_same_metric(self):
        registry = Registry()
        one = registry.counter("hits_total", "hits")
        two = registry.counter("hits_total", "hits")
        assert one is two


class TestRender:
    def test_the_render_is_sorted_and_commented(self):
        registry = Registry()
        registry.gauge("zeta", "last").set(1)
        registry.counter("alpha_total", "first").bump()
        page = registry.render()
        assert page.index("alpha_total") < page.index("zeta")
        assert "# first" in page

    def test_whole_gauges_render_without_the_point(self):
        registry = Registry()
        registry.gauge("count", "a count").set(3.0)
        assert "count 3" in registry.render()


class TestScrape:
    def test_the_sim_numbers_arrive_named(self):
        sim = Sim()
        sim.add_nodes(2)
        sim.deploys.append(
            DeploySpec(
                name="web",
                replicas=3,
                template=TaskSpec(name="tpl", needs=Resources(cpu=100, memory=100)),
            )
        )
        sim.run(5)
        page = scrape(sim).render()
        assert "scheduler_placed_total 3" in page
        assert "tasks_running 3" in page
        assert "nodes_total 2" in page
