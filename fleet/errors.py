"""The failure vocabulary: every raise in the package speaks one of these."""

from __future__ import annotations


class FleetError(Exception):
    """Base for everything the package raises on purpose."""


class Invalid(FleetError):
    """A spec that cannot be admitted: negative resources, empty names."""


class Conflict(FleetError):
    """A stale write: the object changed since the reader loaded it."""


class NotFound(FleetError):
    """A name that resolves to nothing."""


class Unschedulable(FleetError):
    """No node passes the filters; carries the per-node reasons."""

    def __init__(self, reasons: dict[str, str]) -> None:
        self.reasons = dict(reasons)
        text = "; ".join(f"{node}: {why}" for node, why in sorted(reasons.items()))
        super().__init__(text or "no nodes exist")
