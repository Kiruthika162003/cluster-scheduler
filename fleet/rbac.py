"""Who may do what: roles are verb sets, bindings are people, denials say why.

A role names the verbs it grants, scoped to a namespace or to the whole
fleet. A binding hands a role to a person. The gate answers allow or
deny before any verb runs, and a denial names the missing grant rather
than the word forbidden, because the difference between you need
fleet-admin and computer says no is a ticket that resolves itself. The
reader role exists so that read verbs never need a decision at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid

READ_VERBS = frozenset({"get", "list", "watch"})
CHANGE_VERBS = frozenset(
    {"submit", "delete", "apply", "scale", "cordon", "uncordon", "drain"}
)


@dataclass(frozen=True)
class Role:
    name: str
    verbs: frozenset[str]
    namespace: str | None = None

    def __post_init__(self) -> None:
        unknown = self.verbs - READ_VERBS - CHANGE_VERBS
        if unknown:
            raise Invalid(f"role {self.name}: unknown verbs {sorted(unknown)}")


READER = Role(name="reader", verbs=READ_VERBS)
OPERATOR = Role(name="operator", verbs=READ_VERBS | CHANGE_VERBS)


@dataclass
class Gate:
    roles: dict[str, Role] = field(default_factory=dict)
    bindings: dict[str, list[str]] = field(default_factory=dict)
    denials: list[str] = field(default_factory=list)

    def define(self, role: Role) -> None:
        self.roles[role.name] = role

    def bind(self, who: str, role_name: str) -> None:
        if role_name not in self.roles:
            raise Invalid(f"role {role_name} is not defined")
        self.bindings.setdefault(who, []).append(role_name)

    def may(self, who: str, verb: str, namespace: str | None = None) -> tuple[bool, str]:
        granted_by = []
        for role_name in self.bindings.get(who, []):
            role = self.roles[role_name]
            if verb not in role.verbs:
                continue
            if role.namespace is not None and role.namespace != namespace:
                continue
            granted_by.append(role_name)
        if granted_by:
            return True, f"granted by {granted_by[0]}"
        scope = f" in {namespace}" if namespace else ""
        denial = f"{who} may not {verb}{scope}: no binding grants it"
        self.denials.append(denial)
        return False, denial


def standard_gate() -> Gate:
    gate = Gate()
    gate.define(READER)
    gate.define(OPERATOR)
    return gate
