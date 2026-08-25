from __future__ import annotations

from fleet.deadman import Deadman


class TestDeadman:
    def test_a_beating_controller_never_pages(self):
        deadman = Deadman(allowance=5)
        for now in range(20):
            deadman.beat("deployer", now)
            assert deadman.sweep(now) == []

    def test_a_never_started_controller_is_grace_not_death(self):
        deadman = Deadman(allowance=5)
        deadman.register("slowboot")
        assert deadman.sweep(now=100) == []
        assert deadman.standing(100) == ["slowboot: never checked in"]

    def test_silence_after_the_first_beat_pages_once(self):
        deadman = Deadman(allowance=5)
        deadman.beat("deployer", now=0)
        assert deadman.sweep(now=6) == [
            "[6] deployer silent 6, allowance 5"
        ]
        assert deadman.sweep(now=7) == []

    def test_a_recovery_rearms_the_page(self):
        deadman = Deadman(allowance=5)
        deadman.beat("deployer", now=0)
        deadman.sweep(now=6)
        deadman.beat("deployer", now=7)
        assert deadman.sweep(now=13) == [
            "[13] deployer silent 6, allowance 5"
        ]

    def test_the_sweep_names_every_silent_controller(self):
        deadman = Deadman(allowance=3)
        deadman.beat("a", now=0)
        deadman.beat("b", now=0)
        pages = deadman.sweep(now=4)
        assert len(pages) == 2

    def test_standing_reports_ages(self):
        deadman = Deadman(allowance=5)
        deadman.beat("deployer", now=2)
        assert deadman.standing(now=10) == ["deployer: 8 ago"]
