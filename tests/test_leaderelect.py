from __future__ import annotations

from fleet.leaderelect import LEASE_TICKS, Controller, Election, FencedLog


class TestTheLease:
    def test_the_vacant_lease_goes_to_the_first_candidate(self):
        election = Election()
        assert election.campaign("a", now=0) == 1
        assert election.leader(0) == "a"

    def test_the_second_candidate_waits(self):
        election = Election()
        election.campaign("a", now=0)
        assert election.campaign("b", now=1) is None

    def test_renewal_keeps_the_same_token(self):
        election = Election()
        assert election.campaign("a", now=0) == 1
        assert election.campaign("a", now=5) == 1

    def test_an_expired_lease_is_taken_with_a_higher_token(self):
        election = Election()
        election.campaign("a", now=0)
        token = election.campaign("b", now=LEASE_TICKS)
        assert token == 2
        assert election.leader(LEASE_TICKS) == "b"

    def test_resignation_opens_the_seat_now(self):
        election = Election()
        election.campaign("a", now=0)
        assert election.resign("a", now=3)
        assert election.campaign("b", now=3) == 2

    def test_nobody_leads_between_reigns(self):
        election = Election()
        election.campaign("a", now=0)
        assert election.leader(LEASE_TICKS) is None

    def test_handovers_are_a_readable_history(self):
        election = Election()
        election.campaign("a", now=0)
        election.campaign("b", now=LEASE_TICKS)
        assert election.handovers == [
            "[0] nobody -> a (token 1)",
            f"[{LEASE_TICKS}] a -> b (token 2)",
        ]


class TestFencing:
    def test_the_stale_token_bounces(self):
        log = FencedLog()
        assert log.write("surge web", token=2)
        assert not log.write("surge web again", token=1)
        assert log.accepted == ["surge web"]
        assert "token 1 < 2" in log.fenced[0]

    def test_equal_tokens_still_write(self):
        log = FencedLog()
        assert log.write("first", token=3)
        assert log.write("second", token=3)


class TestTheWholeStory:
    def test_the_woken_straggler_cannot_corrupt(self):
        election = Election()
        log = FencedLog()
        old = Controller(name="old", election=election, log=log)
        new = Controller(name="new", election=election, log=log)

        assert old.tick(0, work="step rollout") == "did step rollout"
        assert new.tick(LEASE_TICKS, work="step rollout") == "did step rollout"

        old.token = 1
        assert not log.write("late write from the past", token=old.token)
        assert log.accepted == ["step rollout", "step rollout"]

    def test_standby_does_no_work(self):
        election = Election()
        log = FencedLog()
        leader = Controller(name="a", election=election, log=log)
        standby = Controller(name="b", election=election, log=log)
        leader.tick(0, work="w")
        assert standby.tick(1, work="w") == "standby"
        assert standby.acted == 0

    def test_the_new_leader_carries_on_after_a_silent_death(self):
        election = Election()
        log = FencedLog()
        a = Controller(name="a", election=election, log=log)
        b = Controller(name="b", election=election, log=log)
        for now in range(5):
            a.tick(now, work=f"a{now}")
        outcome = b.tick(5 + LEASE_TICKS, work="b0")
        assert outcome == "did b0"
        assert log.highest_seen == 2
