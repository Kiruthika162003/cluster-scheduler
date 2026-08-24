"""Every trial, one call, one report."""

from __future__ import annotations

import importlib

from fleet.trials.verdict import Verdict

TRIALS = (
    "fleet.trials.fragmentation",
    "fleet.trials.ghosts",
    "fleet.trials.cascade",
    "fleet.trials.oscillation",
    "fleet.trials.drainfloor",
    "fleet.trials.rolloutpace",
    "fleet.trials.canaryevidence",
    "fleet.trials.overcommit",
    "fleet.trials.ganghostages",
    "fleet.trials.slivers",
    "fleet.trials.warmupdebt",
    "fleet.trials.packing",
    "fleet.trials.chaosfloor",
    "fleet.trials.moneybill",
    "fleet.trials.starvation",
    "fleet.trials.kernelwalk",
    "fleet.trials.spotnotice",
    "fleet.trials.softstep",
    "fleet.trials.noisyfair",
    "fleet.trials.splitbrain",
    "fleet.trials.rollbacklag",
    "fleet.trials.filterorder",
    "fleet.trials.balloonpay",
    "fleet.trials.twobills",
    "fleet.trials.wrongprobe",
)


def all_verdicts() -> list[Verdict]:
    made = []
    for name in TRIALS:
        module = importlib.import_module(name)
        made.append(module.run())
    return made


def broken() -> list[str]:
    return [verdict.trial for verdict in all_verdicts() if not verdict.holds]


def report() -> str:
    lines = ["fleet trials"]
    lines.append("=" * 40)
    for verdict in all_verdicts():
        lines.append(verdict.line())
    failing = broken()
    lines.append("")
    lines.append(
        f"{len(TRIALS)} trials, {len(failing)} broken"
        + (f": {', '.join(failing)}" if failing else "")
    )
    return "\n".join(lines)
