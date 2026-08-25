"""The command line: trials, and the cluster's story on demand."""

from __future__ import annotations

import argparse
import sys

from fleet.conformance import Conformance
from fleet.trials.registry import broken, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fleet")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("trials", help="run every trial and print the report")
    commands.add_parser("check", help="exit nonzero if any trial is broken")
    commands.add_parser("conformance", help="run the conformance suite")
    parsed = parser.parse_args(argv)
    if parsed.command == "trials":
        print(report())
        return 0
    if parsed.command == "conformance":
        suite = Conformance()
        print(suite.report())
        return 1 if suite.failing() else 0
    failing = broken()
    if failing:
        print(f"broken: {', '.join(failing)}")
        return 1
    print("all trials hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
