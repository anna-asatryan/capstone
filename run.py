#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from codes.pipelines.common import ANALYSIS_DIR
from codes.pipelines.rebuild_from_upstream import run_rebuild_from_upstream
from codes.pipelines.reproduce_from_frozen import run_reproduction_from_frozen
from codes.pipelines.validate_artifacts import validate_frozen_artifacts


MENU = """Choose mode:
1. Reproduce main results from frozen artifacts
2. Rebuild from upstream inputs and continue
"""


def choose_mode_interactively() -> str:
    while True:
        print(MENU)
        choice = input("Enter 1 or 2: ").strip()
        if choice == "1":
            return "frozen"
        if choice == "2":
            return "rebuild"
        print("Please enter 1 or 2.\n")


def should_launch_summary(explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    response = input("Launch the summary app now? [Y/n]: ").strip().lower()
    return response in ("", "y", "yes")


def launch_summary_app(data_dir: Path) -> int:
    command = [
        sys.executable,
        "-m",
        "codes.summary_app.app",
        "--data-dir",
        str(data_dir),
    ]
    return subprocess.run(command, cwd=Path(__file__).resolve().parent).returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive reproduction entrypoint for the capstone repository."
    )
    parser.add_argument(
        "--mode",
        choices=["frozen", "rebuild", "validate", "doctor"],
        default="frozen",
        help="frozen (default): reproduce from locked artifacts. rebuild: re-run from raw data. validate/doctor: check integrity.",
    )
    launch_group = parser.add_mutually_exclusive_group()
    launch_group.add_argument(
        "--launch-summary",
        dest="launch_summary",
        action="store_true",
        help="Launch the Dash summary app after the pipeline finishes.",
    )
    launch_group.add_argument(
        "--no-launch-summary",
        dest="launch_summary",
        action="store_false",
        help="Only build downstream outputs; do not launch the summary app.",
    )
    parser.set_defaults(launch_summary=None)
    return parser.parse_args()


def run_mode(mode: str) -> Path | None:
    if mode == "validate":
        result = validate_frozen_artifacts()
        print(
            "Frozen artifacts validated successfully:"
            f" final_cases={result['final_cases']},"
            f" practice_cases={result['practice_cases']},"
            f" candidate_pool_rows={result['candidate_pool_rows']}"
        )
        return None

    if mode == "doctor":
        print(f"Python executable: {sys.executable}")
        print(f"Analysis output directory: {ANALYSIS_DIR}")
        validate_frozen_artifacts()
        print("Frozen artifact validation: OK")
        return None

    if mode == "frozen":
        print("Running deterministic reproduction from official frozen artifacts...\n")
        return run_reproduction_from_frozen(ANALYSIS_DIR)

    print("Running best-effort rebuild from upstream inputs, then continuing into the same analysis flow...\n")
    return run_rebuild_from_upstream(ANALYSIS_DIR)


def main() -> None:
    args = parse_args()
    mode = args.mode
    output_dir = run_mode(mode)

    if output_dir is None:
        return

    print(f"\nAnalysis outputs written to: {output_dir}")
    print("Summary app data bundle is ready.")

    if should_launch_summary(args.launch_summary):
        print("\nStarting the summary app at http://127.0.0.1:8050 ...\n")
        raise SystemExit(launch_summary_app(output_dir))

    print("\nRun `python -m apps.summary_app.app` to open the summary app later.")


if __name__ == "__main__":
    main()
