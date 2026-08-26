from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.migrations import Migration, MigrationPlan, migrate_or_explain


class TestConvergence:
    def test_a_quiet_task_cuts_over_in_one_round(self):
        migration = migrate_or_explain(
            memory=100, dirty_rate=0, copy_rate=50, pause_budget=2
        )
        assert migration.verdict == "cut over after 1 rounds with a 2-tick pause"
        assert migration.downtime() == 2

    def test_rounds_shrink_when_the_link_outpaces_the_writes(self):
        migration = migrate_or_explain(
            memory=1000, dirty_rate=10, copy_rate=100, pause_budget=1
        )
        dirties = [entry.remaining_dirty for entry in migration.rounds]
        assert dirties == [100, 0]
        assert migration.verdict.startswith("cut over after 2 rounds")

    def test_the_pause_respects_its_budget(self):
        migration = migrate_or_explain(
            memory=1000, dirty_rate=10, copy_rate=100, pause_budget=1
        )
        assert migration.downtime() <= 1


class TestDivergence:
    def test_writing_faster_than_copying_is_named_plainly(self):
        migration = migrate_or_explain(
            memory=1000, dirty_rate=200, copy_rate=100, pause_budget=1
        )
        assert "will never converge" in migration.verdict
        assert len(migration.rounds) == 1

    def test_near_parity_stalls_instead_of_slowly_converging(self):
        migration = Migration(
            plan=MigrationPlan(
                memory=10000,
                dirty_rate=99,
                copy_rate=100,
                pause_budget=1,
                max_rounds=10,
            )
        )
        migration.run()
        assert "will never converge" in migration.verdict
        assert len(migration.rounds) == 3

    def test_slow_shrink_gives_up_at_the_round_cap(self):
        migration = Migration(
            plan=MigrationPlan(
                memory=10000,
                dirty_rate=50,
                copy_rate=100,
                pause_budget=1,
                max_rounds=3,
            )
        )
        migration.run()
        assert migration.verdict == "gave up after 3 rounds with 1250 still dirty"
        with pytest.raises(Invalid):
            migration.downtime()


class TestContracts:
    def test_a_zero_pause_budget_is_refused(self):
        with pytest.raises(Invalid):
            MigrationPlan(memory=10, dirty_rate=0, copy_rate=10, pause_budget=0)

    def test_the_receipt_is_tuning_data(self):
        migration = migrate_or_explain(
            memory=1000, dirty_rate=10, copy_rate=100, pause_budget=1
        )
        page = migration.receipt()
        assert page.splitlines()[1] == (
            "  round 1: copied 1000 in 10 ticks, 100 redirtied"
        )
        assert "round 2: copied 100 in 1 ticks, 0 redirtied" in page
