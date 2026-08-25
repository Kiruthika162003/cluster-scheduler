"""Declarative apply: the manifest is wanted, the plan is the difference.

A manifest is plain data naming deployments, quotas and budgets. Plan
compares it against the store and lists what would be created, changed
or deleted, without touching anything; apply executes exactly the plan
it printed, because an apply that diverges from its plan is a lie with
a progress bar. Unknown keys are refused at parse time: a typo that
silently becomes a default is the worst bug a config system can ship.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.control.budget import Budget, Guard
from fleet.control.deploy import DeploySpec
from fleet.control.nsquota import Admission, NamespaceQuota
from fleet.errors import Invalid
from fleet.objects import Resources, TaskSpec

DEPLOY_KEYS = {"name", "replicas", "cpu", "memory", "labels", "namespace"}
QUOTA_KEYS = {"namespace", "max_tasks", "max_cpu", "max_memory"}
BUDGET_KEYS = {"name", "selector_key", "selector_value", "min_available"}


@dataclass(frozen=True)
class Manifest:
    deploys: tuple[DeploySpec, ...] = ()
    quotas: tuple[NamespaceQuota, ...] = ()
    budgets: tuple[Budget, ...] = ()


def _refuse_unknown(entry: dict, allowed: set[str], kind: str) -> None:
    unknown = set(entry) - allowed
    if unknown:
        raise Invalid(f"{kind}: unknown keys {sorted(unknown)}")


def parse(data: dict) -> Manifest:
    deploys = []
    for entry in data.get("deploys", []):
        _refuse_unknown(entry, DEPLOY_KEYS, "deploy")
        if "name" not in entry or "replicas" not in entry:
            raise Invalid("deploy: name and replicas are required")
        labels = tuple(sorted((entry.get("labels") or {}).items()))
        deploys.append(
            DeploySpec(
                name=entry["name"],
                replicas=int(entry["replicas"]),
                template=TaskSpec(
                    name=f"{entry['name']}-template",
                    needs=Resources(
                        cpu=int(entry.get("cpu", 100)),
                        memory=int(entry.get("memory", 100)),
                    ),
                    namespace=entry.get("namespace", "default"),
                    labels=labels,
                ),
            )
        )
    quotas = []
    for entry in data.get("quotas", []):
        _refuse_unknown(entry, QUOTA_KEYS, "quota")
        quotas.append(
            NamespaceQuota(
                namespace=entry["namespace"],
                max_tasks=int(entry.get("max_tasks", 10**6)),
                max_requests=Resources(
                    cpu=int(entry.get("max_cpu", 10**9)),
                    memory=int(entry.get("max_memory", 10**9)),
                ),
            )
        )
    budgets = []
    for entry in data.get("budgets", []):
        _refuse_unknown(entry, BUDGET_KEYS, "budget")
        budgets.append(
            Budget(
                name=entry["name"],
                selector_key=entry["selector_key"],
                selector_value=entry["selector_value"],
                min_available=int(entry["min_available"]),
            )
        )
    unknown_top = set(data) - {"deploys", "quotas", "budgets"}
    if unknown_top:
        raise Invalid(f"manifest: unknown sections {sorted(unknown_top)}")
    return Manifest(
        deploys=tuple(deploys), quotas=tuple(quotas), budgets=tuple(budgets)
    )


@dataclass
class Plan:
    create: list[str] = field(default_factory=list)
    change: list[str] = field(default_factory=list)
    delete: list[str] = field(default_factory=list)

    def empty(self) -> bool:
        return not (self.create or self.change or self.delete)

    def lines(self) -> str:
        made = []
        for verb, names in (
            ("create", self.create),
            ("change", self.change),
            ("delete", self.delete),
        ):
            made.extend(f"{verb} {name}" for name in names)
        return "\n".join(made) if made else "nothing to do"


@dataclass
class Applier:
    """Holds the applied manifest state and reconciles deployments from it."""

    held: dict[str, DeploySpec] = field(default_factory=dict)
    applies: int = 0

    def plan(self, manifest: Manifest) -> Plan:
        made = Plan()
        wanted = {spec.name: spec for spec in manifest.deploys}
        for name in sorted(wanted):
            if name not in self.held:
                made.create.append(f"deploy/{name}")
            elif self.held[name] != wanted[name]:
                made.change.append(f"deploy/{name}")
        for name in sorted(self.held):
            if name not in wanted:
                made.delete.append(f"deploy/{name}")
        return made

    def apply(self, manifest: Manifest, store, deployer) -> Plan:
        made = self.plan(manifest)
        wanted = {spec.name: spec for spec in manifest.deploys}
        for line in made.delete:
            name = line.split("/", 1)[1]
            gone = self.held.pop(name)
            empty = DeploySpec(name=name, replicas=0, template=gone.template)
            deployer.reconcile(store, empty)
        for name, spec in wanted.items():
            self.held[name] = spec
            deployer.reconcile(store, spec)
        self.applies += 1
        return made

def gates_from(manifest: Manifest):
    """The admission gate and budget guard the manifest describes.

    Quotas become an Admission, budgets become a Guard, and both are
    fresh objects: the manifest is the source of truth and the gates are
    disposable projections of it, rebuilt on every apply rather than
    patched, because patching projections is how they drift.
    """
    admission = Admission(quotas={quota.namespace: quota for quota in manifest.quotas})
    guard = Guard(budgets=list(manifest.budgets))
    return admission, guard
