"""Spec diffs in sentences: what applying this would actually change.

A plan that says change deploy/web is a plan that makes the reviewer
open two files. The diff says web: replicas 3 to 5, cpu 200m to 400m,
label tier added as front, and suddenly the review is the reading.
Unchanged fields say nothing, because a diff that repeats the whole
object is the object, and order is stable so two diffs of the same
change are the same text.
"""

from __future__ import annotations

from fleet.control.deploy import DeploySpec
from fleet.objects import TaskSpec


def task_spec_diff(before: TaskSpec, after: TaskSpec) -> list[str]:
    lines = []
    if before.needs.cpu != after.needs.cpu:
        lines.append(f"cpu {before.needs.cpu}m to {after.needs.cpu}m")
    if before.needs.memory != after.needs.memory:
        lines.append(
            f"memory {before.needs.memory}Mi to {after.needs.memory}Mi"
        )
    if before.priority != after.priority:
        lines.append(f"priority {before.priority} to {after.priority}")
    if before.namespace != after.namespace:
        lines.append(
            f"namespace {before.namespace} to {after.namespace}"
        )
    mine = before.label_map()
    theirs = after.label_map()
    for key in sorted(set(mine) | set(theirs)):
        if key not in theirs:
            lines.append(f"label {key} removed, was {mine[key]}")
        elif key not in mine:
            lines.append(f"label {key} added as {theirs[key]}")
        elif mine[key] != theirs[key]:
            lines.append(
                f"label {key} {mine[key]} to {theirs[key]}"
            )
    return lines


def deploy_diff(before: DeploySpec, after: DeploySpec) -> list[str]:
    lines = []
    if before.replicas != after.replicas:
        lines.append(f"replicas {before.replicas} to {after.replicas}")
    lines.extend(task_spec_diff(before.template, after.template))
    return [f"{after.name}: {line}" for line in lines]


def describe(before: DeploySpec | None, after: DeploySpec | None) -> list[str]:
    if before is None and after is not None:
        return [f"{after.name}: created with {after.replicas} replicas"]
    if after is None and before is not None:
        return [f"{before.name}: deleted, had {before.replicas} replicas"]
    if before is None or after is None:
        return []
    told = deploy_diff(before, after)
    return told or [f"{after.name}: no changes"]
