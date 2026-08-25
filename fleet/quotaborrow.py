"""Quota borrowing: idle guarantees are lent out and called back with notice.

Each team holds a guaranteed quota; the lender pools whatever guarantee
its owner is not using and lends it to teams over their line. The loan
is honest about its one hard truth: borrowed capacity is a loan, and
when the owner returns, the call comes with a notice window, after
which the borrower's overage is evicted eldest first. Teams that plan
on borrowed capacity staying are planning on their neighbor's absence,
and the call ledger prices that plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass
class Account:
    team: str
    guarantee: int
    used: int = 0
    borrowed: int = 0


@dataclass
class Lender:
    accounts: dict[str, Account] = field(default_factory=dict)
    notice_window: int = 5
    calls: dict[str, int] = field(default_factory=dict)
    evictions: list[str] = field(default_factory=list)

    def open_account(self, team: str, guarantee: int) -> None:
        if team in self.accounts:
            raise Invalid(f"{team} already has an account")
        self.accounts[team] = Account(team=team, guarantee=guarantee)

    def _idle_pool(self) -> int:
        return sum(
            max(0, held.guarantee - held.used)
            for held in self.accounts.values()
        )

    def _borrowed_total(self) -> int:
        return sum(held.borrowed for held in self.accounts.values())

    def use(self, team: str, amount: int) -> str:
        account = self.accounts[team]
        within = min(amount, max(0, account.guarantee - account.used))
        account.used += within
        overflow = amount - within
        if overflow == 0:
            return f"{team} within guarantee"
        available = self._idle_pool() - self._borrowed_total()
        if overflow > available:
            raise Invalid(
                f"{team} wants {overflow} borrowed, pool holds {available}"
            )
        account.used += overflow
        account.borrowed += overflow
        return f"{team} borrowed {overflow}"

    def owner_returns(self, team: str, amount: int, now: int) -> list[str]:
        """The owner wants its guarantee back; borrowers get called."""
        shortfall = amount - (self._idle_pool() - self._borrowed_total())
        told = []
        if shortfall > 0:
            for debtor in sorted(
                self.accounts.values(), key=lambda held: held.team
            ):
                if shortfall <= 0 or debtor.borrowed == 0:
                    continue
                called = min(debtor.borrowed, shortfall)
                self.calls[debtor.team] = now + self.notice_window
                told.append(
                    f"{debtor.team} called for {called}, "
                    f"due {now + self.notice_window}"
                )
                shortfall -= called
        self.use(team, amount)
        return told

    def enforce(self, now: int) -> list[str]:
        evicted = []
        for team, due in sorted(self.calls.items()):
            if now < due:
                continue
            account = self.accounts[team]
            if account.borrowed > 0:
                evicted.append(
                    f"{team}: {account.borrowed} borrowed evicted at {now}"
                )
                account.used -= account.borrowed
                account.borrowed = 0
            del self.calls[team]
        self.evictions.extend(evicted)
        return evicted
