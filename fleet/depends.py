"""Dependencies: web starts after db, cycles are refused, outages cascade.

A deployment may declare what it needs running before it starts. The
graph refuses cycles at declaration, computes the start order
topologically, and the gate holds a deployment at zero until its needs
are met. The other direction is the one dashboards forget: when a
dependency dies, everything downstream of it is impaired at once, and
blast() names that set so the incident channel does not have to
discover it service by service.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass
class DependencyGraph:
    needs: dict[str, set[str]] = field(default_factory=dict)

    def declare(self, service: str, needs: str) -> None:
        if service == needs:
            raise Invalid(f"{service} cannot need itself")
        walk = [needs]
        seen = set()
        while walk:
            current = walk.pop()
            if current == service:
                raise Invalid(
                    f"{service} needing {needs} would close a cycle"
                )
            if current in seen:
                continue
            seen.add(current)
            walk.extend(self.needs.get(current, set()))
        self.needs.setdefault(service, set()).add(needs)
        self.needs.setdefault(needs, set())

    def start_order(self) -> list[str]:
        order = []
        placed: set[str] = set()
        remaining = dict(self.needs)
        while remaining:
            ready = sorted(
                name
                for name, wants in remaining.items()
                if wants <= placed
            )
            if not ready:
                raise Invalid("the graph is stuck, which should be impossible")
            for name in ready:
                order.append(name)
                placed.add(name)
                del remaining[name]
        return order

    def may_start(self, service: str, running: set[str]) -> tuple[bool, str]:
        missing = sorted(self.needs.get(service, set()) - running)
        if missing:
            return False, f"waiting on {', '.join(missing)}"
        return True, "all needs met"

    def blast(self, failed: str) -> list[str]:
        """Everything downstream of a failure, the failure excluded."""
        hit = []
        for service in self.needs:
            if service == failed:
                continue
            walk = list(self.needs.get(service, set()))
            seen = set()
            while walk:
                current = walk.pop()
                if current == failed:
                    hit.append(service)
                    break
                if current in seen:
                    continue
                seen.add(current)
                walk.extend(self.needs.get(current, set()))
        return sorted(hit)
