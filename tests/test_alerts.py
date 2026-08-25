from __future__ import annotations

from fleet.alerts import Event, Pager


def flap_storm(pager: Pager, ticks: int = 40) -> Pager:
    for tick in range(ticks):
        state = "down" if (tick // 2) % 2 == 0 else "up"
        pager.take(Event(tick=tick, subject="n1", state=state))
    pager.settle("n1", ticks)
    return pager


class TestDedup:
    def test_identical_alerts_inside_the_window_fold(self):
        pager = Pager(dedup_window=10, flap_threshold=10**6)
        for tick in range(5):
            pager.take(Event(tick=tick, subject="disk", state="full"))
        assert len(pager.pages) == 1
        assert pager.folded == 4

    def test_the_window_expiring_repages(self):
        pager = Pager(dedup_window=10, flap_threshold=10**6)
        pager.take(Event(tick=0, subject="disk", state="full"))
        pager.take(Event(tick=10, subject="disk", state="full"))
        assert len(pager.pages) == 2

    def test_a_state_change_pages_immediately(self):
        pager = Pager(dedup_window=10, flap_threshold=10**6)
        pager.take(Event(tick=0, subject="disk", state="full"))
        pager.take(Event(tick=1, subject="disk", state="ok"))
        assert len(pager.pages) == 2


class TestFlapping:
    def test_the_storm_becomes_four_pages(self):
        pager = flap_storm(Pager())
        assert len(pager.pages) == 4
        assert "flapping" in pager.pages[2]
        assert pager.pages[3] == "[40] n1 settled: up"

    def test_the_raw_pager_babbles(self):
        pager = flap_storm(Pager(dedup_window=0, flap_threshold=10**6))
        assert len(pager.pages) == 40

    def test_settling_reopens_normal_paging(self):
        pager = flap_storm(Pager())
        pager.take(Event(tick=50, subject="n1", state="down"))
        assert pager.pages[-1] == "[50] n1 down"

    def test_settle_without_a_flap_is_silent(self):
        pager = Pager()
        pager.settle("quiet", 5)
        assert pager.pages == []

    def test_two_subjects_do_not_share_a_flap(self):
        pager = Pager()
        flap_storm(pager)
        pager.take(Event(tick=41, subject="n2", state="down"))
        assert pager.pages[-1] == "[41] n2 down"
