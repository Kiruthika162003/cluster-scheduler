from __future__ import annotations

from examples import incident, launchday, multiteam, simweek, upgrade


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
