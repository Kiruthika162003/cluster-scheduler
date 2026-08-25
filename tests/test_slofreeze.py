from __future__ import annotations

from fleet.objects import Node, Resources, TaskSpec
from fleet.roll.rolling import Roller, Rollout
from fleet.slo import SloBoard, SloSpec
from fleet.slofreeze import SloFreezeGate
from fleet.store import Store


def board_with(web_good: int) -> SloBoard:
    board = SloBoard()
    board.watch(SloSpec(name="web", objective=0.99, window=1000))
    for tick in range(10):
        board.observe("web", tick, good=web_good, total=100)
    return board


def rollout() -> tuple[Store, Rollout]:
    store = Store()
    store.add_node(Node(name="n0", capacity=Resources(cpu=1000, memory=1000)))
    roll = Rollout(
        name="web",
        replicas=2,
        template=TaskSpec(name="web", needs=Resources(cpu=100, memory=100)),
        revision=2,
    )
    return store, roll


class TestTheGate:
    def test_a_healthy_budget_ships(self):
        gate = SloFreezeGate(board=board_with(web_good=100))
        allowed, why = gate.may_ship("web")
        assert allowed
        assert why == "budget healthy"

    def test_a_bankrupt_budget_refuses(self):
        gate = SloFreezeGate(board=board_with(web_good=50))
        allowed, why = gate.may_ship("web")
        assert not allowed
        assert why == "error budget exhausted"
        assert gate.denials["web"] == 1

    def test_unwatched_deploys_are_not_frozen(self):
        gate = SloFreezeGate(board=board_with(web_good=50))
        allowed, _ = gate.may_ship("sidecar-updater")
        assert allowed


class TestBrokenGlass:
    def test_the_glass_names_its_breaker(self):
        gate = SloFreezeGate(board=board_with(web_good=50))
        gate.break_glass("web", "meera", "security patch", now=7)
        allowed, why = gate.may_ship("web")
        assert allowed
        assert why == "glass broken by meera: security patch"

    def test_recovery_sweeps_the_glass_away(self):
        board = board_with(web_good=50)
        gate = SloFreezeGate(board=board)
        gate.break_glass("web", "meera", "security patch", now=7)
        for tick in range(2000, 2010):
            board.observe("web", tick, good=100, total=100)
        allowed, why = gate.may_ship("web")
        assert allowed
        assert why == "budget healthy"
        assert "web" not in gate.broken


class TestSteppingTheRoller:
    def test_a_frozen_deploy_does_not_advance(self):
        gate = SloFreezeGate(board=board_with(web_good=50))
        store, roll = rollout()
        outcome = gate.step(Roller(), store, roll)
        assert outcome == "frozen: error budget exhausted"
        assert store.tasks == {}

    def test_a_healthy_deploy_rolls_through_the_gate(self):
        gate = SloFreezeGate(board=board_with(web_good=100))
        store, roll = rollout()
        outcome = gate.step(Roller(), store, roll)
        assert outcome == "surged"
        assert len(store.tasks) == 1


class TestReport:
    def test_the_report_counts_teeth_marks(self):
        gate = SloFreezeGate(board=board_with(web_good=50))
        gate.may_ship("web")
        gate.may_ship("web")
        gate.break_glass("web", "raj", "rollback fix", now=9)
        page = gate.report()
        assert "1 frozen, 1 glasses broken" in page
        assert "web: 2 rolls refused" in page
        assert "shipping on broken glass (raj: rollback fix)" in page
