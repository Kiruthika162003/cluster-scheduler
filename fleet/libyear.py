"""Dependency freshness: staleness has a unit, and the unit is libyears.

"Our dependencies are pretty current" is a feeling; the libyear
metric is a number: for each dependency, the time between the
version you run and the newest version available, summed across
the manifest. One package four years stale scores the same as
sixteen packages three months stale, which is correct, because
both describe the same volume of unreviewed change waiting to
surprise you. The ledger tracks each dependency's release history,
scores the manifest, and splits the total into the head you could
fix this week (many small laggards) and the tail you must plan for
(the ancient pin someone is afraid of), because the two shares
need different meetings.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid, NotFound

TAIL_THRESHOLD = 300


@dataclass
class ReleaseHistory:
    versions: list[tuple[str, int]] = field(default_factory=list)

    def released(self, version: str, at: int) -> None:
        if self.versions and at < self.versions[-1][1]:
            raise Invalid("releases must arrive in order")
        self.versions.append((version, at))

    def age_behind(self, running: str) -> int:
        stamped = dict(self.versions)
        if running not in stamped:
            raise NotFound(f"version {running} was never released")
        newest_at = self.versions[-1][1]
        return newest_at - stamped[running]


@dataclass
class FreshnessLedger:
    histories: dict[str, ReleaseHistory] = field(default_factory=dict)
    manifest: dict[str, str] = field(default_factory=dict)

    def track(self, package: str) -> ReleaseHistory:
        history = self.histories.setdefault(package, ReleaseHistory())
        return history

    def pin(self, package: str, version: str) -> None:
        if package not in self.histories:
            raise NotFound(f"{package} has no release history")
        self.manifest[package] = version

    def libyears(self) -> dict[str, int]:
        if not self.manifest:
            raise Invalid("an empty manifest scores nothing")
        return {
            package: self.histories[package].age_behind(version)
            for package, version in sorted(self.manifest.items())
        }

    def total(self) -> int:
        return sum(self.libyears().values())

    def head_and_tail(self) -> tuple[int, int]:
        head = tail = 0
        for age in self.libyears().values():
            if age >= TAIL_THRESHOLD:
                tail += age
            else:
                head += age
        return head, tail

    def statement(self) -> str:
        ages = self.libyears()
        head, tail = self.head_and_tail()
        lines = [
            f"{self.total()} libyears across {len(ages)} pins "
            f"(head {head}, tail {tail})"
        ]
        for package, age in sorted(
            ages.items(), key=lambda row: (-row[1], row[0])
        ):
            mark = " [plan]" if age >= TAIL_THRESHOLD else ""
            lines.append(f"  {package}: {age} behind{mark}")
        return "\n".join(lines)
