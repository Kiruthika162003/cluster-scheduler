from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.redundancymath import (
    Tier,
    best_marginal_replica,
    chain,
    replicas,
    statement,
    topology,
)


class TestComposition:
    def test_chains_multiply_down(self):
        assert chain(0.99, 0.99, 0.99) == pytest.approx(0.970299)

    def test_the_chain_is_worse_than_its_weakest_link(self):
        assert chain(0.999, 0.9) < 0.9

    def test_replicas_multiply_up(self):
        assert replicas(0.9, 2) == pytest.approx(0.99)

    def test_two_mediocre_nines_make_a_good_one(self):
        assert replicas(0.99, 2) == pytest.approx(0.9999)

    def test_an_empty_chain_is_refused(self):
        with pytest.raises(Invalid):
            chain()

    def test_certainty_is_not_an_input(self):
        with pytest.raises(Invalid):
            replicas(1.0, 2)
        with pytest.raises(Invalid):
            Tier(name="x", single=1.0, count=1)


class TestTopology:
    def three_tiers(self) -> list[Tier]:
        return [
            Tier(name="balancer", single=0.999, count=2),
            Tier(name="app", single=0.99, count=3),
            Tier(name="db", single=0.995, count=2),
        ]

    def test_the_topology_gets_a_number_not_a_shrug(self):
        assert topology(self.three_tiers()) == pytest.approx(
            0.999973, abs=1e-6
        )

    def test_the_next_replica_goes_where_feelings_do_not(self):
        name, gain = best_marginal_replica(self.three_tiers())
        assert name == "db"
        assert gain == pytest.approx(2.487e-05, abs=1e-7)

    def test_the_statement_reads_the_whole_argument(self):
        page = statement(self.three_tiers())
        lines = page.splitlines()
        assert lines[0] == "balancer: 2 x 0.999 -> 0.999999"
        assert lines[3] == "topology: 0.999973"
        assert lines[4].startswith("next replica belongs in db")

    def test_no_tiers_is_refused(self):
        with pytest.raises(Invalid):
            topology([])
