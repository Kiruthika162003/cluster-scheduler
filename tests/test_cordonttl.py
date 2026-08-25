from __future__ import annotations

from fleet.audit import Journal
from fleet.cordonttl import CordonLeases
from fleet.objects import Node, Resources
from fleet.store import Store


def rig() -> tuple[Store, Journal, CordonLeases]:
    store = Store()
    for number in range(2):
        store.add_node(
            Node(name=f"n{number}", capacity=Resources(cpu=1000, memory=1000))
        )
    return store, Journal(), CordonLeases(default_ttl=10)


class TestLeases:
    def test_a_cordon_takes_effect_and_records_its_reason(self):
        store, journal, leases = rig()
        leases.cordon(store, journal, "n0", "meera", "disk swap", now=0)
        assert not store.get_node("n0").schedulable
        assert "disk swap" in journal.story("n0")

    def test_an_unexpired_lease_survives_the_sweep(self):
        store, journal, leases = rig()
        leases.cordon(store, journal, "n0", "meera", "disk swap", now=0)
        assert leases.sweep(store, journal, now=9) == []
        assert not store.get_node("n0").schedulable

    def test_expiry_uncordons_and_journals_the_forgetter(self):
        store, journal, leases = rig()
        leases.cordon(store, journal, "n0", "meera", "disk swap", now=0)
        released = leases.sweep(store, journal, now=10)
        assert released == ["n0"]
        assert store.get_node("n0").schedulable
        assert "lease from meera expired" in journal.story("n0")

    def test_renewal_extends_the_lease(self):
        store, journal, leases = rig()
        leases.cordon(store, journal, "n0", "meera", "disk swap", now=0)
        leases.renew("n0", now=8)
        assert leases.sweep(store, journal, now=15) == []
        assert leases.sweep(store, journal, now=18) == ["n0"]

    def test_a_departed_node_expires_without_error(self):
        store, journal, leases = rig()
        leases.cordon(store, journal, "n0", "meera", "decommission", now=0)
        store.remove_node("n0")
        assert leases.sweep(store, journal, now=10) == ["n0"]

    def test_standing_reads_oldest_first(self):
        store, journal, leases = rig()
        leases.cordon(store, journal, "n1", "raj", "later", now=5, ttl=100)
        leases.cordon(store, journal, "n0", "meera", "earlier", now=1, ttl=100)
        told = leases.standing(now=6)
        assert told[0].startswith("n0: meera, earlier, held 5")
        assert told[1].startswith("n1: raj, later, held 1")
