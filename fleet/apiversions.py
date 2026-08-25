"""API versions: old clients speak v1 forever, the hub speaks one truth.

Objects are stored at the hub version; every other version converts on
the way in and the way out. The conversion pair must round-trip
losslessly for fields both versions share, and deliberately, visibly
drop what the old version cannot say, recording each drop, because
silent lossy conversion is how a v1 client erases a v2 field it never
knew existed. The compatibility test is written once against the pair
and runs for every version in the table.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.errors import Invalid
from fleet.objects import Resources, TaskSpec

HUB = "v2"


def to_v1(spec: TaskSpec) -> dict:
    return {
        "version": "v1",
        "name": spec.name,
        "cpu": spec.needs.cpu,
        "memory": spec.needs.memory,
        "labels": dict(spec.labels),
    }


def from_v1(data: dict) -> TaskSpec:
    return TaskSpec(
        name=data["name"],
        needs=Resources(cpu=data["cpu"], memory=data["memory"]),
        labels=tuple(sorted(data.get("labels", {}).items())),
    )


def to_v2(spec: TaskSpec) -> dict:
    return {
        "version": "v2",
        "name": spec.name,
        "cpu": spec.needs.cpu,
        "memory": spec.needs.memory,
        "labels": dict(spec.labels),
        "namespace": spec.namespace,
        "priority": spec.priority,
        "tolerates": list(spec.tolerates),
    }


def from_v2(data: dict) -> TaskSpec:
    return TaskSpec(
        name=data["name"],
        needs=Resources(cpu=data["cpu"], memory=data["memory"]),
        labels=tuple(sorted(data.get("labels", {}).items())),
        namespace=data.get("namespace", "default"),
        priority=data.get("priority", 0),
        tolerates=tuple(data.get("tolerates", ())),
    )


CONVERTERS = {
    "v1": (to_v1, from_v1),
    "v2": (to_v2, from_v2),
}

V1_DROPS = ("namespace", "priority", "tolerates")


@dataclass
class Gateway:
    drops: list[str] = field(default_factory=list)

    def read(self, spec: TaskSpec, version: str) -> dict:
        if version not in CONVERTERS:
            raise Invalid(f"unknown version {version}")
        serialize, _ = CONVERTERS[version]
        if version == "v1":
            for field_name in V1_DROPS:
                value = getattr(spec, field_name)
                default = TaskSpec(
                    name="probe", needs=Resources(cpu=0, memory=0)
                )
                if value != getattr(default, field_name):
                    self.drops.append(
                        f"{spec.name}: v1 cannot carry {field_name}"
                    )
        return serialize(spec)

    def write(self, data: dict) -> TaskSpec:
        version = data.get("version")
        if version not in CONVERTERS:
            raise Invalid(f"unknown version {version}")
        _, deserialize = CONVERTERS[version]
        return deserialize(data)
