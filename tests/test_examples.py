from __future__ import annotations

from examples import (
    batchnight,
    blackfriday,
    execmonthly,
    fullday,
    gameday,
    incident,
    launchday,
    multiteam,
    nocweek,
    opsreview,
    patchtuesday,
    quarterreview,
    regionfailover,
    releasetrain,
    simweek,
    storefront,
    stormdrill,
    streamnight,
    upgrade,
)


class TestBlackFriday:
    def test_the_surge_lands_and_the_balloon_pays(self, capsys):
        assert blackfriday.main() == 0
        out = capsys.readouterr().out
        assert "no, only 1800m after bookings" in out
        assert "checkout surge running at tick 50, balloons popped 1" in out
        assert "batch finished 2 of 2" in out


class TestExecMonthly:
    def test_the_owner_reads_one_screen(self, capsys):
        assert execmonthly.main() == 0
        out = capsys.readouterr().out
        assert "n+1: ok, survives losing n3" in out
        assert "platform-idle 20304.0" in out
        assert "ml: up 350%, 8000 to 36000" in out
        assert "ml: +133% of the move" in out


class TestOpsReview:
    def test_five_ledgers_one_meeting(self, capsys):
        assert opsreview.main() == 0
        out = capsys.readouterr().out
        assert "checkout: 3 outages, 94.0000% available" in out
        assert "change failure rate: 20%" in out
        assert "n0 vs CVE-1: 6 past deadline" in out
        assert "ghost: n9 works here but nobody approved it" in out
        assert "440 libyears across 2 pins (head 40, tail 400)" in out


class TestStreamNight:
    def test_the_night_reads_honestly(self, capsys):
        assert streamnight.main() == 0
        out = capsys.readouterr().out
        assert "2 stragglers (0 dropped, 2 windows corrected)" in out
        assert "137 points held from 2000, the 200.0 spike survives" in out
        assert "robust flags ['n9'], z-score flags []" in out
        assert "3am at 102: normal for this hour" in out
        assert "noon at 450: hole" in out


class TestStormDrill:
    def test_the_quartet_holds_the_line(self, capsys):
        assert stormdrill.main() == 0
        out = capsys.readouterr().out
        assert "breaker: closed, saved 29 waits" in out
        assert "amplification 1.012" in out
        assert "backend spared 88 calls against the naive client" in out
        assert "db: 2/2 running, 1/1 queued, 3 refused" in out
        assert "p99 300 -> 62 for 5.0% extra load" in out


class TestQuarterReview:
    def test_the_three_answers_land_on_one_page(self, capsys):
        assert quarterreview.main() == 0
        out = capsys.readouterr().out
        assert "full around tick 268 (window 267 to 268)" in out
        assert "headroom: 2800m -> 4800m" in out
        assert "1240.0W burning now, 200.0W recoverable" in out


class TestNocWeek:
    def test_the_week_reads_end_to_end(self, capsys):
        assert nocweek.main() == 0
        out = capsys.readouterr().out
        assert "tuesday: prober says up, 1 page(s) sent, first to meera" in out
        assert "wednesday: checkout frozen (error budget exhausted)" in out
        assert "thursday: n2 quarantined, schedulable=False" in out
        assert "node-triage: 40m [automated by quarantine warden]" in out


class TestFullDay:
    def test_the_day_reads_end_to_end(self, capsys):
        assert fullday.main() == 0
        out = capsys.readouterr().out
        assert "morning: 6 tasks running across 4 nodes" in out
        assert "paging meera of storefront" in out
        assert "batch pipeline done, order extract, transform, load" in out
        assert "one node retired at noon, capacity is tighter" in out


class TestGameday:
    def test_the_worst_storm_replays_and_the_brief_closes_clean(self, capsys):
        assert gameday.main() == 0
        out = capsys.readouterr().out
        assert "campaign floor across 25 storms: 4 of 8" in out
        assert "replayed seed 13: truthful floor 4 (campaign said 4)" in out
        assert "all 45 conformance checks hold" in out


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
        assert "all 45 conformance checks hold" in out


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
