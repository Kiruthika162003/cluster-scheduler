"""Backfill: reserved capacity earns rent between now and its window.

A hold for tomorrow's launch leaves cpu idle today, and idle paid-for
cpu is the most expensive kind. The backfiller lends held capacity
to scavenger work with an eviction deadline stamped at admission:
the loan ends when the hold's window opens, no negotiation, and only
work that declares it can finish (or checkpoint) inside the loan may
borrow. At the window's edge the backfiller evicts its own tenants
first, which is the difference between lending and losing the
capacity; the receipt reports utilisation bought and evictions paid,
because backfill is only a win while the first number dwarfs the
second.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.holds import Hold, HoldLedger


@dataclass(frozen=True)
class Loan:
    task: str
    hold: str
    cpu: int
    granted_at: int
    due_at: int


@dataclass
class Backfiller:
    ledger: HoldLedger
    loans: dict[str, Loan] = field(default_factory=dict)
    lent_ticks: int = 0
    evictions: int = 0
    finished: int = 0

    def idle_held(self, node: str, now: int) -> list[Hold]:
        return [
            hold
            for hold in self.ledger.holds.values()
            if hold.node == node and hold.starts > now
        ]

    def borrow(
        self, task: str, cpu: int, needs_ticks: int, node: str, now: int
    ) -> Loan | None:
        if task in self.loans:
            raise Invalid(f"{task} already holds a loan")
        for hold in sorted(
            self.idle_held(node, now), key=lambda held: held.starts
        ):
            lent = sum(
                loan.cpu
                for loan in self.loans.values()
                if loan.hold == hold.name
            )
            if lent + cpu > hold.amount.cpu:
                continue
            deadline = hold.starts
            if now + needs_ticks > deadline:
                continue
            loan = Loan(
                task=task,
                hold=hold.name,
                cpu=cpu,
                granted_at=now,
                due_at=deadline,
            )
            self.loans[task] = loan
            return loan
        return None

    def finish(self, task: str, now: int) -> None:
        loan = self.loans.pop(task, None)
        if loan is None:
            raise Invalid(f"{task} holds no loan")
        self.lent_ticks += (min(now, loan.due_at) - loan.granted_at) * loan.cpu
        self.finished += 1

    def sweep(self, now: int) -> list[str]:
        """The window's edge: evict every loan that has come due."""
        evicted = []
        for task in sorted(self.loans):
            loan = self.loans[task]
            if now >= loan.due_at:
                del self.loans[task]
                self.lent_ticks += (loan.due_at - loan.granted_at) * loan.cpu
                self.evictions += 1
                evicted.append(task)
        return evicted

    def receipt(self) -> str:
        return (
            f"{self.lent_ticks} cpu-ticks lent, {self.finished} finished, "
            f"{self.evictions} evicted"
        )
