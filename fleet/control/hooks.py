"""Admission hooks: mutators shape the object, validators judge the result.

Hooks run in two phases with a hard wall between them: every mutator
first, in registration order, then every validator against the final
shape. A validator that runs before a later mutator would judge an
object that never existed, which is the bug this ordering exists to
prevent, and the chain records what each hook did so a surprising
object can be traced to the hook that made it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace

from fleet.errors import Invalid
from fleet.objects import Resources, TaskSpec


@dataclass
class Chain:
    mutators: list[tuple[str, Callable[[TaskSpec], TaskSpec]]] = field(
        default_factory=list
    )
    validators: list[tuple[str, Callable[[TaskSpec], str | None]]] = field(
        default_factory=list
    )
    trace: list[str] = field(default_factory=list)
    refusals: int = 0

    def mutate_with(self, name: str, hook: Callable[[TaskSpec], TaskSpec]) -> None:
        self.mutators.append((name, hook))

    def validate_with(self, name: str, hook: Callable[[TaskSpec], str | None]) -> None:
        self.validators.append((name, hook))

    def admit(self, spec: TaskSpec) -> TaskSpec:
        shaped = spec
        for name, hook in self.mutators:
            before = shaped
            shaped = hook(shaped)
            if shaped != before:
                self.trace.append(f"{name} reshaped {spec.name}")
        for name, hook in self.validators:
            refusal = hook(shaped)
            if refusal is not None:
                self.refusals += 1
                self.trace.append(f"{name} refused {spec.name}: {refusal}")
                raise Invalid(f"{name}: {refusal}")
        self.trace.append(f"admitted {spec.name}")
        return shaped


def default_labels(**defaults: str) -> Callable[[TaskSpec], TaskSpec]:
    def hook(spec: TaskSpec) -> TaskSpec:
        held = spec.label_map()
        missing = {key: value for key, value in defaults.items() if key not in held}
        if not missing:
            return spec
        return replace(
            spec, labels=tuple(sorted({**held, **missing}.items()))
        )

    return hook


def minimum_resources(cpu: int, memory: int) -> Callable[[TaskSpec], TaskSpec]:
    def hook(spec: TaskSpec) -> TaskSpec:
        needs = spec.needs
        raised = Resources(
            cpu=max(needs.cpu, cpu), memory=max(needs.memory, memory)
        )
        if raised == needs:
            return spec
        return replace(spec, needs=raised)

    return hook


def refuse_label(key: str, value: str) -> Callable[[TaskSpec], str | None]:
    def hook(spec: TaskSpec) -> str | None:
        if spec.label_map().get(key) == value:
            return f"label {key}={value} is not allowed"
        return None

    return hook


def require_label(key: str) -> Callable[[TaskSpec], str | None]:
    def hook(spec: TaskSpec) -> str | None:
        if key not in spec.label_map():
            return f"label {key} is required"
        return None

    return hook
