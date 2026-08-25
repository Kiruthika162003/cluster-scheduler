"""The text front for manifests: a format small enough to have no dark corners.

Sections are bare words ending with a colon, entries are dash lines,
fields are key = value pairs indented beneath, comments start with a
hash. That is the whole grammar. Errors carry line numbers because a
config error without one costs a binary search through the file, and
the parser hands its output straight to the dict parser so there is
exactly one place meaning is decided.
"""

from __future__ import annotations

from fleet.errors import Invalid
from fleet.manifest import Manifest, parse

SECTIONS = ("deploys", "quotas", "budgets")
INT_FIELDS = {
    "replicas", "cpu", "memory", "max_tasks", "max_cpu", "max_memory",
    "min_available",
}


def parse_text(text: str) -> Manifest:
    data: dict[str, list[dict]] = {}
    section: str | None = None
    entry: dict | None = None
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" "):
            name = line.rstrip(":")
            if not line.endswith(":") or name not in SECTIONS:
                raise Invalid(f"line {lineno}: expected a section, got {raw!r}")
            section = name
            data[section] = []
            entry = None
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            if section is None:
                raise Invalid(f"line {lineno}: entry outside any section")
            entry = {}
            data[section].append(entry)
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if "=" not in stripped:
            raise Invalid(f"line {lineno}: expected key = value, got {raw!r}")
        if entry is None:
            raise Invalid(f"line {lineno}: field before any entry")
        key, value = (part.strip() for part in stripped.split("=", 1))
        if key in INT_FIELDS:
            try:
                entry[key] = int(value)
            except ValueError as wrong:
                raise Invalid(
                    f"line {lineno}: {key} wants a number, got {value!r}"
                ) from wrong
        elif key == "labels":
            pairs = {}
            for piece in value.split(","):
                if ":" not in piece:
                    raise Invalid(
                        f"line {lineno}: labels want k:v pairs, got {piece!r}"
                    )
                label_key, label_value = piece.split(":", 1)
                pairs[label_key.strip()] = label_value.strip()
            entry[key] = pairs
        else:
            entry[key] = value
    return parse(data)
