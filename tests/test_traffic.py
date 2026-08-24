from __future__ import annotations

from fleet.roll.traffic import Splitter


class TestAssignment:
    def test_the_share_shapes_arrivals(self):
        splitter = Splitter(canary_share=0.3)
        splitter.tick(0, new_users=10)
        assert splitter.arrivals == {"stable": 7, "canary": 3}

    def test_zero_share_sends_nobody(self):
        splitter = Splitter(canary_share=0.0)
        splitter.tick(0, new_users=10)
        assert splitter.arrivals["canary"] == 0

    def test_full_share_sends_everybody(self):
        splitter = Splitter(canary_share=1.0)
        splitter.tick(0, new_users=10)
        assert splitter.arrivals["canary"] == 10


class TestSessions:
    def test_sessions_expire_after_their_length(self):
        splitter = Splitter(canary_share=0.0, session_length=5)
        splitter.tick(0, new_users=4)
        assert splitter.population()["stable"] == 4
        splitter.tick(5, new_users=0)
        assert splitter.population()["stable"] == 0

    def test_a_caught_user_stays_after_the_dial_moves(self):
        splitter = Splitter(canary_share=1.0, session_length=50)
        splitter.tick(0, new_users=5)
        splitter.canary_share = 0.0
        splitter.tick(1, new_users=5)
        counts = splitter.population()
        assert counts["canary"] == 5 and counts["stable"] == 5

    def test_the_population_share_lags_the_dial(self):
        splitter = Splitter(canary_share=0.5, session_length=10)
        for now in range(20):
            splitter.tick(now, new_users=4)
        splitter.canary_share = 0.0
        splitter.tick(20, new_users=4)
        assert splitter.canary_population_share() > 0.0

    def test_an_empty_splitter_has_no_share(self):
        assert Splitter().canary_population_share() == 0.0
