from __future__ import annotations

from fleet.failover import Pair, Site, Watcher, partition_story


def fresh_pair(promote_after: int = 2) -> Pair:
    return Pair(
        east=Site(name="east", role="active"),
        west=Site(name="west"),
        watcher=Watcher(promote_after=promote_after),
    )


class TestWatcher:
    def test_a_healthy_active_resets_the_count(self):
        pair = fresh_pair(promote_after=2)
        pair.tick(east_up=False, east_reachable=False)
        pair.tick(east_up=True, east_reachable=True)
        pair.tick(east_up=False, east_reachable=False)
        assert pair.watcher.promotions == 0

    def test_consecutive_failures_promote(self):
        pair = fresh_pair(promote_after=2)
        pair.tick(east_up=False, east_reachable=False)
        pair.tick(east_up=False, east_reachable=False)
        assert pair.west.role == "active"
        assert pair.watcher.promotions == 1

    def test_a_dead_passive_is_never_promoted(self):
        pair = fresh_pair(promote_after=1)
        pair.tick(east_up=False, east_reachable=False, west_up=False)
        assert pair.west.role == "passive"
        assert pair.outage_ticks == 1


class TestRolesAndMeters:
    def test_a_partitioned_active_keeps_serving_its_side(self):
        pair = fresh_pair(promote_after=1)
        pair.tick(east_up=True, east_reachable=False)
        pair.tick(east_up=True, east_reachable=False)
        assert pair.split_brain_ticks >= 1

    def test_a_dead_active_keeps_its_stale_crown_harmlessly(self):
        pair = fresh_pair(promote_after=1)
        pair.tick(east_up=False, east_reachable=False)
        assert pair.west.role == "active"
        assert pair.east.role == "active" and not pair.east.serving()
        pair.tick(east_up=True, east_reachable=True)
        assert pair.east.role == "passive"

    def test_a_healed_returner_follows_the_crown(self):
        pair = fresh_pair(promote_after=1)
        pair.tick(east_up=True, east_reachable=False)
        pair.tick(east_up=True, east_reachable=False)
        pair.tick(east_up=True, east_reachable=True)
        assert pair.east.role == "passive"
        assert pair.split_brain_ticks == 2

    def test_history_names_the_servers(self):
        pair = fresh_pair(promote_after=1)
        pair.tick(east_up=True, east_reachable=True)
        assert pair.history == ["east"]


class TestStory:
    def test_the_story_is_deterministic(self):
        one = partition_story(3)
        two = partition_story(3)
        assert one.history == two.history

    def test_every_watcher_promotes_exactly_once(self):
        for promote_after in (1, 3, 10):
            assert partition_story(promote_after).watcher.promotions == 1
