from __future__ import annotations

from fleet.cooldowns import PreemptionCooldowns


class TestImmunity:
    def test_a_fresh_task_is_not_immune(self):
        cooldowns = PreemptionCooldowns(window=10)
        assert not cooldowns.immune("batch", now=0)

    def test_displacement_grants_the_window(self):
        cooldowns = PreemptionCooldowns(window=10)
        cooldowns.note_displacement("batch", now=5)
        assert cooldowns.immune("batch", now=14)
        assert not cooldowns.immune("batch", now=15)

    def test_shields_are_counted(self):
        cooldowns = PreemptionCooldowns(window=10)
        cooldowns.note_displacement("batch", now=0)
        cooldowns.immune("batch", now=1)
        cooldowns.immune("batch", now=2)
        assert cooldowns.shielded == 2


class TestThePinballMeter:
    def test_the_count_covers_the_span(self):
        cooldowns = PreemptionCooldowns(window=5)
        for tick in (0, 20, 40, 200):
            cooldowns.note_displacement("batch", tick)
        assert cooldowns.pinball_count("batch", span=60, now=60) == 3

    def test_the_worst_pinball_is_named(self):
        cooldowns = PreemptionCooldowns(window=5)
        cooldowns.note_displacement("calm", 0)
        for tick in (0, 10, 20):
            cooldowns.note_displacement("pinball", tick)
        assert cooldowns.worst_pinball(span=60, now=30) == ("pinball", 3)

    def test_an_empty_ledger_has_no_worst(self):
        assert PreemptionCooldowns(window=5).worst_pinball(60, 0) is None
