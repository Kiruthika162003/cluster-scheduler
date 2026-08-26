"""The wait graph: deadlock is a cycle, so find cycles, not symptoms.

A gang holds half its members and waits for quota; the quota waits
on a namespace whose tasks wait for the gang to release nodes.
Nothing is broken, everything is waiting, and the queue metrics all
read "busy". The graph records who waits on whom, detects cycles by
depth-first search, and names the full loop in order, because the
fix is always to break one specific edge and the operator needs to
see which edges exist to pick the cheapest. Waiters outside any
cycle get their distance to one, since a task four hops behind a
deadlock is stuck just as hard but shows up in no cycle report.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid


@dataclass
class WaitGraph:
    edges: dict[str, dict[str, str]] = field(default_factory=dict)

    def waits(self, waiter: str, holder: str, why: str) -> None:
        if waiter == holder:
            raise Invalid(f"{waiter} cannot wait on itself")
        self.edges.setdefault(waiter, {})[holder] = why

    def released(self, waiter: str, holder: str) -> None:
        held = self.edges.get(waiter, {})
        held.pop(holder, None)
        if not held:
            self.edges.pop(waiter, None)

    def cycles(self) -> list[list[str]]:
        found: list[list[str]] = []
        seen_cycles: set[tuple[str, ...]] = set()
        for start in sorted(self.edges):
            stack = [(start, [start])]
            while stack:
                current, path = stack.pop()
                for holder in sorted(self.edges.get(current, {})):
                    if holder == start and len(path) > 1:
                        loop = path[:]
                        smallest = min(range(len(loop)), key=lambda i: loop[i])
                        canon = tuple(loop[smallest:] + loop[:smallest])
                        if canon not in seen_cycles:
                            seen_cycles.add(canon)
                            found.append(list(canon))
                    elif holder == start:
                        loop = [start]
                        canon = (start,)
                        if canon not in seen_cycles:
                            seen_cycles.add(canon)
                            found.append([start])
                    elif holder not in path:
                        stack.append((holder, [*path, holder]))
        return sorted(found)

    def blocked_behind(self, cycle: list[str]) -> dict[str, int]:
        """Waiters outside the cycle, with their hop distance to it."""
        inside = set(cycle)
        distance: dict[str, int] = {}
        changed = True
        while changed:
            changed = False
            for waiter in sorted(self.edges):
                if waiter in inside or waiter in distance:
                    continue
                hops = None
                for holder in self.edges[waiter]:
                    if holder in inside:
                        hops = 1
                    elif holder in distance:
                        candidate = distance[holder] + 1
                        hops = candidate if hops is None else min(hops, candidate)
                if hops is not None:
                    distance[waiter] = hops
                    changed = True
        return distance

    def report(self) -> str:
        loops = self.cycles()
        if not loops:
            waiting = len(self.edges)
            return f"no deadlock: {waiting} waiters, all making progress"
        lines = [f"{len(loops)} deadlock(s)"]
        for loop in loops:
            steps = []
            for index, waiter in enumerate(loop):
                holder = loop[(index + 1) % len(loop)]
                why = self.edges[waiter].get(holder, "?")
                steps.append(f"{waiter} waits on {holder} ({why})")
            lines.append("  " + " -> ".join(steps))
            stuck = self.blocked_behind(loop)
            for name in sorted(stuck):
                lines.append(f"    {name} is {stuck[name]} hop(s) behind")
        return "\n".join(lines)
