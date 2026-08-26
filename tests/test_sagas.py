from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.sagas import Saga, Step


class World:
    def __init__(self, drain_works: bool = True):
        self.cordoned = False
        self.drained = False
        self.snapshotted = False
        self.removed = False
        self.drain_works = drain_works

    def steps(self) -> list[Step]:
        def cordon() -> bool:
            self.cordoned = True
            return True

        def uncordon() -> None:
            self.cordoned = False

        def drain() -> bool:
            self.drained = self.drain_works
            return self.drain_works

        def undrain() -> None:
            self.drained = False

        def snapshot() -> bool:
            self.snapshotted = True
            return True

        def drop_snapshot() -> None:
            self.snapshotted = False

        def remove() -> bool:
            self.removed = True
            return True

        return [
            Step("cordon", cordon, uncordon),
            Step("drain", drain, undrain),
            Step("snapshot", snapshot, drop_snapshot),
            Step("remove", remove, None),
        ]


class TestForward:
    def test_a_clean_run_completes_in_order(self):
        world = World()
        saga = Saga(name="decommission n3", steps=world.steps())
        assert saga.run() == "completed all 4 steps"
        assert world.removed

    def test_the_ledger_reads_as_a_story(self):
        world = World()
        saga = Saga(name="decommission n3", steps=world.steps())
        saga.run()
        assert saga.story().splitlines() == [
            "decommission n3: completed all 4 steps",
            "  did cordon",
            "  did drain",
            "  did snapshot",
            "  did remove",
        ]


class TestUnwinding:
    def test_a_mid_saga_failure_undoes_in_reverse(self):
        world = World(drain_works=False)
        saga = Saga(name="decommission n3", steps=world.steps())
        outcome = saga.run()
        assert outcome == "failed at drain, unwound 1 steps"
        assert not world.cordoned
        assert saga.ledger == [
            "did cordon",
            "FAILED drain",
            "undid cordon",
        ]

    def test_socks_off_after_shoes(self):
        order = []
        steps = [
            Step("shoes", lambda: order.append("on-shoes") or True,
                 lambda: order.append("off-shoes")),
            Step("socks", lambda: order.append("on-socks") or True,
                 lambda: order.append("off-socks")),
            Step("fails", lambda: False, lambda: None),
        ]
        Saga(name="dressing", steps=steps).run()
        assert order == ["on-shoes", "on-socks", "off-socks", "off-shoes"]


class TestThePointOfNoReturn:
    def test_irreversible_middles_are_refused_by_default(self):
        steps = [
            Step("wipe disks", lambda: True, None),
            Step("remove", lambda: True, None),
        ]
        with pytest.raises(Invalid, match="wipe disks"):
            Saga(name="risky", steps=steps)

    def test_the_caller_can_accept_the_risk_explicitly(self):
        steps = [
            Step("wipe disks", lambda: True, None),
            Step("fails", lambda: False, lambda: None),
        ]
        saga = Saga(name="risky", steps=steps, accepts_no_return=True)
        saga.run()
        assert "cannot undo wipe disks: past the point of no return" in (
            saga.ledger
        )

    def test_an_irreversible_last_step_is_fine(self):
        steps = [
            Step("cordon", lambda: True, lambda: None),
            Step("remove", lambda: True, None),
        ]
        assert Saga(name="ok", steps=steps).run() == "completed all 2 steps"

    def test_an_empty_saga_is_refused(self):
        with pytest.raises(Invalid):
            Saga(name="hollow", steps=[])
