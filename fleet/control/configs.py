"""Config objects and the hash stamp: edits that restart, edits that ghost.

A config is data tasks read at start. Editing it in place changes what
future tasks will see and nothing about running ones, which is how a
fleet ends up serving three configs at once with one name. The hash
stamp closes the gap: the deployment template carries a label with the
config's content hash, so a config edit changes the template, and a
changed template is exactly what a rollout notices. Without the stamp
the edit is a ghost; with it, the edit is a deploy, which is what it
always was.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace

from fleet.control.deploy import DeploySpec
from fleet.errors import NotFound
from fleet.objects import TaskSpec


def content_hash(data: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for key in sorted(data):
        digest.update(key.encode())
        digest.update(b"=")
        digest.update(data[key].encode())
        digest.update(b";")
    return digest.hexdigest()[:12]


@dataclass
class ConfigBook:
    configs: dict[str, dict[str, str]] = field(default_factory=dict)
    edits: int = 0

    def put(self, name: str, data: dict[str, str]) -> str:
        if name in self.configs:
            self.edits += 1
        self.configs[name] = dict(data)
        return content_hash(self.configs[name])

    def get(self, name: str) -> dict[str, str]:
        if name not in self.configs:
            raise NotFound(f"config {name}")
        return dict(self.configs[name])

    def hash_of(self, name: str) -> str:
        return content_hash(self.get(name))

    def stamped_template(self, template: TaskSpec, config_name: str) -> TaskSpec:
        labels = dict(template.labels)
        labels[f"config-{config_name}"] = self.hash_of(config_name)
        return replace(template, labels=tuple(sorted(labels.items())))

    def stamped_deploy(self, spec: DeploySpec, config_name: str) -> DeploySpec:
        return DeploySpec(
            name=spec.name,
            replicas=spec.replicas,
            template=self.stamped_template(spec.template, config_name),
        )


def serving_hashes(store, deploy_name: str, config_name: str) -> set[str]:
    """Which config hashes the fleet is actually running right now."""
    key = f"config-{config_name}"
    return {
        task.spec.label_map().get(key, "unstamped")
        for task in store.tasks.values()
        if task.spec.label_map().get("deploy") == deploy_name
    }
