"""Readiness gating on dependencies: web is not ready until db answers.

The dependency graph says web needs db; the endpoints say whether db
currently answers. The gate composes them: a service's tasks report
unready while any dependency has zero endpoints, without restarting
anything, and recover the moment the dependency does. The cascade this
prevents is the familiar one: web marked ready with a dead db serves
errors with a healthy face, the balancer keeps sending traffic, and
the outage report says web when it means db.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.control.endpoints import Readiness, Service, endpoints
from fleet.depends import DependencyGraph
from fleet.store import Store


@dataclass
class ReadyGate:
    graph: DependencyGraph
    services: dict[str, Service] = field(default_factory=dict)
    gated_now: set[str] = field(default_factory=set)
    transitions: list[str] = field(default_factory=list)

    def register(self, service: Service) -> None:
        self.services[service.name] = service

    def _has_endpoints(
        self, store: Store, name: str, readiness: Readiness, now: int
    ) -> bool:
        service = self.services.get(name)
        if service is None:
            return False
        return bool(endpoints(store, service, readiness, now))

    def gated_services(
        self, store: Store, readiness: Readiness, now: int
    ) -> set[str]:
        gated = set()
        for name in self.services:
            needs = self.graph.needs.get(name, set())
            for dependency in needs:
                if not self._has_endpoints(store, dependency, readiness, now):
                    gated.add(name)
                    break
        for name in sorted(gated - self.gated_now):
            self.transitions.append(f"[{now}] {name} gated")
        for name in sorted(self.gated_now - gated):
            self.transitions.append(f"[{now}] {name} released")
        self.gated_now = gated
        return gated

    def effective_endpoints(
        self, store: Store, name: str, readiness: Readiness, now: int
    ) -> list[str]:
        gated = self.gated_services(store, readiness, now)
        if name in gated:
            return []
        service = self.services.get(name)
        if service is None:
            return []
        return endpoints(store, service, readiness, now)
