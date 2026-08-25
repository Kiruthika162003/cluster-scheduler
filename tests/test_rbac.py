from __future__ import annotations

import pytest

from fleet.errors import Invalid
from fleet.rbac import CHANGE_VERBS, OPERATOR, READER, Gate, Role, standard_gate


class TestRoles:
    def test_unknown_verbs_are_refused_at_definition(self):
        with pytest.raises(Invalid):
            Role(name="odd", verbs=frozenset({"yeet"}))

    def test_the_reader_reads_and_nothing_else(self):
        assert "get" in READER.verbs
        assert not (READER.verbs & CHANGE_VERBS)

    def test_the_operator_holds_every_verb(self):
        assert OPERATOR.verbs >= CHANGE_VERBS


class TestGate:
    def bound_gate(self) -> Gate:
        gate = standard_gate()
        gate.define(
            Role(
                name="search-operator",
                verbs=frozenset({"submit", "delete", "scale"}),
                namespace="search",
            )
        )
        gate.bind("meera", "search-operator")
        gate.bind("meera", "reader")
        gate.bind("admin", "operator")
        return gate

    def test_binding_an_undefined_role_is_refused(self):
        with pytest.raises(Invalid):
            standard_gate().bind("nobody", "ghost-role")

    def test_a_namespace_role_grants_inside_its_namespace(self):
        gate = self.bound_gate()
        allowed, why = gate.may("meera", "scale", namespace="search")
        assert allowed and "search-operator" in why

    def test_the_same_role_denies_outside_its_namespace(self):
        gate = self.bound_gate()
        allowed, why = gate.may("meera", "scale", namespace="ads")
        assert not allowed
        assert "no binding grants it" in why

    def test_the_denial_names_person_verb_and_scope(self):
        gate = self.bound_gate()
        _, why = gate.may("meera", "drain", namespace="search")
        assert why == "meera may not drain in search: no binding grants it"

    def test_reads_pass_everywhere_for_readers(self):
        gate = self.bound_gate()
        allowed, _ = gate.may("meera", "list", namespace="ads")
        assert allowed

    def test_the_fleet_operator_passes_everywhere(self):
        gate = self.bound_gate()
        for verb in CHANGE_VERBS:
            assert gate.may("admin", verb, namespace="anything")[0]

    def test_a_stranger_is_denied_and_counted(self):
        gate = self.bound_gate()
        allowed, _ = gate.may("stranger", "delete")
        assert not allowed
        assert len(gate.denials) == 1
