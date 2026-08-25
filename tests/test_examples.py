from __future__ import annotations

from examples import (
    batchnight,
    blackfriday,
    gameday,
    incident,
    launchday,
    multiteam,
    patchtuesday,
    regionfailover,
    releasetrain,
    simweek,
    storefront,
    upgrade,
)


class TestBlackFriday:
    def test_the_surge_lands_and_the_balloon_pays(self, capsys):
        assert blackfriday.main() == 0
        out = capsys.readouterr().out
        assert "no, only 1800m after bookings" in out
        assert "checkout surge running at tick 50, balloons popped 1" in out
        assert "batch finished 2 of 2" in out


class TestGameday:
    def test_the_worst_storm_replays_and_the_brief_closes_clean(self, capsys):
        assert gameday.main() == 0
        out = capsys.readouterr().out
        assert "campaign floor across 25 storms: 4 of 8" in out
        assert "replayed seed 13: truthful floor 4 (campaign said 4)" in out
        assert "all 12 conformance checks hold" in out


class TestIncident:
    def test_the_incident_recovers_fully(self, capsys):
        assert incident.main() == 0
        out = capsys.readouterr().out
        assert "running at the end 12" in out
        assert "provisioned 1 replacement node(s)" in out
        assert "worst running count after the failure: 8" in out


class TestLaunchday:
    def test_the_launch_scales_and_shares(self, capsys):
        assert launchday.main() == 0
        out = capsys.readouterr().out
        assert "peak 25 replicas" in out
        assert "dominant share 0.669" in out and "dominant share 0.664" in out


class TestMultiteam:
    def test_the_two_teams_settle_where_the_quotas_say(self, capsys):
        assert multiteam.main() == 0
        out = capsys.readouterr().out
        assert "refused ads/greedy" in out and "900m" in out
        assert "admitted search/tiny at 50m" in out
        assert "headroom" in out and "refusals 1" in out


class TestBatchnight:
    def test_three_nights_all_finish_with_the_flakes_retried(self, capsys):
        assert batchnight.main() == 0
        out = capsys.readouterr().out
        assert "rebuild-run0 done at tick 4" in out
        assert "rebuild-run2 done at tick 204" in out
        assert "launched 24 tasks for 18 completions, retried 6" in out


class TestStorefront:
    def test_the_platform_story_ends_clean(self, capsys):
        assert storefront.main() == 0
        out = capsys.readouterr().out
        assert "rollout complete: 4 of 4 available" in out
        assert "refused ['shop-r2-1', 'shop-r2-2', 'shop-r2-3']" in out
        assert "nothing; invariants hold" in out
        assert "all 12 conformance checks hold" in out


class TestPatchTuesday:
    def test_the_calendar_holds_then_the_walk_holds_the_floor(self, capsys):
        assert patchtuesday.main() == 0
        out = capsys.readouterr().out
        assert "tick 10: walk refused by the calendar, opens at 30" in out
        assert "patched 4 nodes, serving floor 8" in out
        assert "final serving: 8 of 8" in out


class TestRegionFailover:
    def test_the_morning_sorts_itself(self, capsys):
        assert regionfailover.main() == 0
        out = capsys.readouterr().out
        assert "checkout: failed over to us-east" in out
        assert "gdpr-ledger: unaffected in eu-central" in out
        assert "STRANDED" not in out


class TestReleaseTrain:
    def test_the_bad_build_is_yanked_and_the_fix_rides_through(self, capsys):
        assert releasetrain.main() == 0
        out = capsys.readouterr().out
        assert "v42 canary verdict: rollback" in out
        assert "stable held at v41 through the freeze" in out
        assert "v43 delivery: delivered after waves" in out
        assert "channels close with stable v43" in out


class TestSimweek:
    def test_the_week_ends_whole_and_clean(self, capsys):
        assert simweek.main() == 0
        out = capsys.readouterr().out
        assert "day 6: running 14, serving 14" in out
        assert "invariants broken 0" in out
        assert "monitor_evictions_total 2" in out
        assert out.count("invariants broken 0") == 7


class TestUpgrade:
    def test_the_bad_build_never_ships(self, capsys):
        assert upgrade.main() == 0
        out = capsys.readouterr().out
        assert "canary verdict on v2: rollback" in out
        assert "builds running now: ['v1']" in out
        assert "after the fixed build: ['v2-fixed']" in out
