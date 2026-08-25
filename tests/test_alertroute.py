from __future__ import annotations

from fleet.alertroute import Dispatch, Router
from fleet.catalog import Catalog, CatalogEntry


def rigged() -> Router:
    catalog = Catalog()
    catalog.register(
        CatalogEntry(
            deploy="web",
            team="storefront",
            channel="#storefront",
            escalation=("meera", "raj", "dana"),
        )
    )
    return Router(catalog=catalog)


class TestFiring:
    def test_a_fresh_alert_reaches_the_owning_channel(self):
        router = rigged()
        dispatch = router.fire("latency-high", "web", now=0)
        assert dispatch == Dispatch(
            alert="latency-high",
            deploy="web",
            channel="#storefront",
            person="meera",
            rung=0,
            at=0,
        )

    def test_the_pager_filter_runs_before_the_catalog(self):
        router = rigged()
        router.fire("latency-high", "web", now=0)
        assert router.fire("latency-high", "web", now=3) is None
        assert len(router.dispatches) == 1

    def test_unowned_deploys_land_on_the_fallback(self):
        router = rigged()
        dispatch = router.fire("crashloop", "ghost", now=0)
        assert dispatch.channel == "#unowned-alerts"
        assert dispatch.person == "whoever-is-watching"


class TestEscalation:
    def test_silence_climbs_the_ladder(self):
        router = rigged()
        router.fire("latency-high", "web", now=0)
        assert router.tick(now=14) == []
        climbed = router.tick(now=15)
        assert [d.person for d in climbed] == ["raj"]
        climbed = router.tick(now=30)
        assert [d.person for d in climbed] == ["dana"]

    def test_the_ladder_has_a_top(self):
        router = rigged()
        router.fire("latency-high", "web", now=0)
        router.tick(now=15)
        router.tick(now=30)
        assert router.tick(now=45) == []

    def test_an_ack_stops_the_climb(self):
        router = rigged()
        router.fire("latency-high", "web", now=0)
        router.ack("latency-high", "web")
        assert router.tick(now=15) == []
        assert router.unheard() == []

    def test_unowned_alerts_never_escalate(self):
        router = rigged()
        router.fire("crashloop", "ghost", now=0)
        assert router.tick(now=15) == []


class TestResolution:
    def test_resolution_clears_the_debt(self):
        router = rigged()
        router.fire("latency-high", "web", now=0)
        router.resolve("latency-high", "web", now=5)
        assert router.unheard() == []
        assert router.tick(now=15) == []

    def test_a_resolved_alert_can_fire_again_later(self):
        router = rigged()
        router.fire("latency-high", "web", now=0)
        router.resolve("latency-high", "web", now=5)
        dispatch = router.fire("latency-high", "web", now=40)
        assert dispatch is not None
        assert dispatch.rung == 0


class TestReport:
    def test_the_report_counts_the_unheard(self):
        router = rigged()
        router.fire("latency-high", "web", now=0)
        router.fire("crashloop", "ghost", now=1)
        router.ack("crashloop", "ghost")
        page = router.report()
        assert page.startswith("2 dispatches, 1 unheard")
        assert "-> meera in #storefront (rung 0)" in page
