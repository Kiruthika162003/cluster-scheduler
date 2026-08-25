"""Redaction: secrets exist, pages do not print them, and the rule is dull.

Any config key matching the secret patterns has its value masked in
every rendered surface: journals, reports, traces. The masking keeps
the length's order of magnitude and the first two characters, enough
to tell two secrets apart in a diff without ever printing one. The
rule is deliberately dull, a name-pattern list, because clever secret
detection has false negatives and a page that prints one secret has
printed too many.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SECRET_MARKERS = ("password", "token", "key", "secret", "credential")


def is_secret_name(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in SECRET_MARKERS)


def mask(value: str) -> str:
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}{'*' * (len(value) - 2)}"


def redact_config(data: dict[str, str]) -> dict[str, str]:
    return {
        key: mask(value) if is_secret_name(key) else value
        for key, value in data.items()
    }


@dataclass
class RedactingRenderer:
    masked: int = 0
    lines: list[str] = field(default_factory=list)

    def render(self, name: str, data: dict[str, str]) -> str:
        shown = []
        for key in sorted(data):
            if is_secret_name(key):
                shown.append(f"  {key} = {mask(data[key])}")
                self.masked += 1
            else:
                shown.append(f"  {key} = {data[key]}")
        page = "\n".join([f"config {name}:", *shown])
        self.lines.append(page)
        return page

    def leaked(self, secrets: list[str]) -> list[str]:
        """The audit: any secret value appearing verbatim in any page."""
        return sorted(
            secret
            for secret in secrets
            if any(secret in page for page in self.lines)
        )
