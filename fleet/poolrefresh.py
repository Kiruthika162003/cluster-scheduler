"""Pool refresh: every machine replaced, one at a time, the fleet never smaller.

An instance refresh walks a pool and replaces each node with a fresh
one of the same shape, provisioning the successor before retiring the
incumbent so capacity never dips below plan. The refresh keeps a
ledger of progress so an interrupted refresh resumes where it stopped
instead of starting over, and the resume is idempotent because the
ledger records names, not counts: a node already replaced is skipped
by name, however many times the refresh restarts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.api import Fleet
from fleet.runbooks import Runbooks


@dataclass
class RefreshLedger:
    pool: list[str]
    replaced: set[str] = field(default_factory=set)
    log: list[str] = field(default_factory=list)

    def remaining(self) -> list[str]:
        return [name for name in self.pool if name not in self.replaced]

    def done(self) -> bool:
        return not self.remaining()


@dataclass
class PoolRefresh:
    books: Runbooks = field(default_factory=Runbooks)

    def step(self, fleet: Fleet, who: str, ledger: RefreshLedger) -> str:
        remaining = ledger.remaining()
        if not remaining:
            return "refresh complete"
        target = remaining[0]
        if target not in fleet.store.nodes:
            ledger.replaced.add(target)
            ledger.log.append(f"{target} already gone, skipped")
            return f"skipped {target}"
        result = self.books.replace_node(fleet, who, target)
        if not result.ran():
            ledger.log.append(f"{target} refused: {result.refused}")
            return f"refused at {target}"
        ledger.replaced.add(target)
        ledger.log.append(f"{target} replaced")
        return f"replaced {target}"

    def run(self, fleet: Fleet, who: str, ledger: RefreshLedger) -> int:
        steps = 0
        while not ledger.done():
            told = self.step(fleet, who, ledger)
            steps += 1
            if told.startswith("refused"):
                break
        return steps
