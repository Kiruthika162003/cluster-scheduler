"""The command line: trials, conformance, and the bench, on demand."""

from __future__ import annotations

import argparse
import sys

from fleet.conformance import Conformance
from fleet.trials.registry import broken, report


def _bench(sizes: str) -> int:
    from fleet.schedbench import Bench

    ladder = []
    for pair in sizes.split(","):
        nodes, _, tasks = pair.partition("x")
        ladder.append((int(nodes), int(tasks)))
    bench = Bench()
    bench.ladder(ladder)
    print(bench.table())
    passed, why = bench.regression_gate()
    print(why)
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fleet")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("trials", help="run every trial and print the report")
    commands.add_parser("check", help="exit nonzero if any trial is broken")
    commands.add_parser("conformance", help="run the conformance suite")
    bench = commands.add_parser(
        "bench", help="measure scheduling complexity over a size ladder"
    )
    bench.add_argument(
        "--sizes",
        default="10x20,20x40,40x80",
        help="comma-separated NODESxTASKS rungs",
    )
    commands.add_parser(
        "summary", help="one line: trials, checks, and their verdicts"
    )
    parsed = parser.parse_args(argv)
    if parsed.command == "trials":
        print(report())
        return 0
    if parsed.command == "conformance":
        suite = Conformance()
        print(suite.report())
        return 1 if suite.failing() else 0
    if parsed.command == "bench":
        return _bench(parsed.sizes)
    if parsed.command == "summary":
        from fleet.trials.registry import TRIALS

        suite = Conformance()
        suite.run()
        failing = broken()
        checks_failing = len(suite.failing())
        print(
            f"{len(TRIALS)} trials ({len(failing)} broken), "
            f"{len(suite.results)} conformance checks "
            f"({checks_failing} failing)"
        )
        return 1 if failing or checks_failing else 0
    failing = broken()
    if failing:
        print(f"broken: {', '.join(failing)}")
        return 1
    print("all trials hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
