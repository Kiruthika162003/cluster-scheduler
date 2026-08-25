"""Network policy: the default decides who has to write the rules.

A policy allows flows from a source selector to a destination selector
on a port. The posture decides everything else: open-by-default means
policies are the exceptions and the operator enumerates dangers;
closed-by-default means policies are the permissions and the operator
enumerates needs. The checker answers can A reach B and, more usefully,
why: the policy that allowed it, or the posture that decided in
silence. Counting the rules each posture requires for the same intent
is the honest comparison, and closed costs more lines and fewer
regrets.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.selector import Clause, matches, parse


@dataclass(frozen=True)
class Policy:
    name: str
    source: tuple[Clause, ...]
    destination: tuple[Clause, ...]
    port: int

    @classmethod
    def allowing(cls, name: str, source: str, destination: str, port: int) -> Policy:
        return cls(
            name=name,
            source=parse(source),
            destination=parse(destination),
            port=port,
        )


@dataclass
class Mesh:
    default_allow: bool
    policies: list[Policy] = field(default_factory=list)
    checks: int = 0

    def allow(self, policy: Policy) -> None:
        self.policies.append(policy)

    def may_reach(
        self,
        source_labels: dict[str, str],
        destination_labels: dict[str, str],
        port: int,
    ) -> tuple[bool, str]:
        self.checks += 1
        for policy in self.policies:
            if (
                policy.port == port
                and matches(policy.source, source_labels)
                and matches(policy.destination, destination_labels)
            ):
                return True, f"allowed by {policy.name}"
        if self.default_allow:
            return True, "allowed by the open default"
        return False, "denied by the closed default"

    def rules_written(self) -> int:
        return len(self.policies)
