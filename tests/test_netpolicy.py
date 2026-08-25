from __future__ import annotations

from fleet.netpolicy import Mesh, Policy


def web() -> dict[str, str]:
    return {"app": "web"}


def db() -> dict[str, str]:
    return {"app": "db"}


def stranger() -> dict[str, str]:
    return {"app": "stranger"}


class TestClosedMesh:
    def closed(self) -> Mesh:
        mesh = Mesh(default_allow=False)
        mesh.allow(Policy.allowing("web-to-db", "app=web", "app=db", 5432))
        return mesh

    def test_the_allowed_flow_passes_with_the_policy_named(self):
        allowed, why = self.closed().may_reach(web(), db(), 5432)
        assert allowed and why == "allowed by web-to-db"

    def test_the_wrong_port_is_denied(self):
        allowed, why = self.closed().may_reach(web(), db(), 3306)
        assert not allowed and "closed default" in why

    def test_a_stranger_is_denied_in_silence(self):
        allowed, why = self.closed().may_reach(stranger(), db(), 5432)
        assert not allowed and why == "denied by the closed default"

    def test_direction_matters(self):
        allowed, _ = self.closed().may_reach(db(), web(), 5432)
        assert not allowed


class TestOpenMesh:
    def test_everything_passes_by_posture(self):
        mesh = Mesh(default_allow=True)
        allowed, why = mesh.may_reach(stranger(), db(), 5432)
        assert allowed and why == "allowed by the open default"

    def test_policies_still_name_themselves_when_they_apply(self):
        mesh = Mesh(default_allow=True)
        mesh.allow(Policy.allowing("web-to-db", "app=web", "app=db", 5432))
        _, why = mesh.may_reach(web(), db(), 5432)
        assert why == "allowed by web-to-db"


class TestPostureCost:
    def test_the_same_intent_costs_more_rules_closed(self):
        services = ["web", "api", "worker"]
        closed = Mesh(default_allow=False)
        for source in services:
            closed.allow(
                Policy.allowing(
                    f"{source}-to-db", f"app={source}", "app=db", 5432
                )
            )
        open_mesh = Mesh(default_allow=True)
        assert closed.rules_written() == 3
        assert open_mesh.rules_written() == 0
        allowed, _ = open_mesh.may_reach(stranger(), db(), 5432)
        assert allowed
        denied, _ = closed.may_reach(stranger(), db(), 5432)
        assert not denied
