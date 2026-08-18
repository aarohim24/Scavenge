"""Thin command-line entry point for CrawlBench."""

from __future__ import annotations

import argparse

from crawlbench.adaptive import format_regimes
from crawlbench.adaptive import run as run_regimes
from crawlbench.benchmark import format_summary, run
from crawlbench.verification.experiment import format_experiment
from crawlbench.verification.experiment import run as run_e0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="crawlbench")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run", help="Run the HTTP and warm Playwright arms")
    subparsers.add_parser("adaptive", help="Run the Crawlee arms across the predictor regimes")
    subparsers.add_parser("e0", help="Run the RAPTURE-style verification experiment")
    args = parser.parse_args(argv)

    if args.command == "adaptive":
        jsonl_path, results = run_regimes()
        print(format_regimes(jsonl_path, results))
        return 0

    if args.command == "e0":
        print(format_experiment(run_e0()))
        return 0

    if args.command not in {None, "run"}:
        parser.error(f"unknown command: {args.command}")

    result = run()
    print(format_summary(result))
    return 0
