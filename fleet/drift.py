"""Drift: the gap between what was applied and what is there, and who wins.

Somebody scales a deployment by hand at 2am; the manifest still says
three. The detector compares the applied intent against the store and
reports drift in sentences. The corrector is the reconciler run again:
the robot puts it back, every time, which is either the feature or the
incident depending on whether the 2am human knew about the robot. The
honest middle is the pause: drift on a paused deployment is reported
and left alone, because sometimes the human at 2am was right.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fleet.control.deploy import Deployer, DeploySpec
from fleet.store import Store


@dataclass(frozen=True)
class Drift:
    deploy: str
    field_name: str
    applied: int
    observed: int

    def sentence(self) -> str:
        return (
            f"{self.deploy}: {self.field_name} applied {self.applied}, "
            f"observed {self.observed}"
        )


@dataclass
class Detector:
    paused: set[str] = field(default_factory=set)
    corrections: int = 0
    respected_pauses: int = 0

    def _observed_replicas(self, store: Store, spec: DeploySpec) -> int:
        return sum(
            1
            for task in store.tasks.values()
            if task.spec.label_map().get("deploy") == spec.name
            and task.phase not in ("Succeeded", "Failed")
        )

    def survey(self, store: Store, applied: list[DeploySpec]) -> list[Drift]:
        found = []
        for spec in applied:
            observed = self._observed_replicas(store, spec)
            if observed != spec.replicas:
                found.append(
                    Drift(
                        deploy=spec.name,
                        field_name="replicas",
                        applied=spec.replicas,
                        observed=observed,
                    )
                )
        return found

    def pause(self, name: str) -> None:
        self.paused.add(name)

    def resume(self, name: str) -> None:
        self.paused.discard(name)

    def correct(
        self, store: Store, applied: list[DeploySpec], deployer: Deployer
    ) -> tuple[list[str], list[str]]:
        """(corrected sentences, respected sentences)."""
        corrected = []
        respected = []
        for drift in self.survey(store, applied):
            if drift.deploy in self.paused:
                self.respected_pauses += 1
                respected.append(drift.sentence())
                continue
            spec = next(s for s in applied if s.name == drift.deploy)
            deployer.reconcile(store, spec)
            self.corrections += 1
            corrected.append(drift.sentence())
        return corrected, respected
