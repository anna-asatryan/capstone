#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEPLOYED_SUMMARY_URL = "https://capstone-explorer.streamlit.app"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AUA DS 299 capstone reproducibility entrypoint."
    )
    parser.add_argument(
        "--mode",
        choices=["paper", "validate", "summary", "rebuild"],
        default="paper",
        help=(
            "paper: reproduce final paper tables/figures from frozen artifacts and exports\n"
            "validate: validate frozen artifacts, design, and exports\n"
            "summary: open deployed summary app or launch local summary app\n"
            "rebuild: optional upstream rebuild from data/raw/loan.csv"
        ),
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Open an interactive mode-selection menu.",
    )
    parser.add_argument(
        "--summary-target",
        choices=["local", "deployed"],
        default="local",
        help=(
            "For summary mode: 'local' launches Streamlit from this repo; "
            "'deployed' opens the public deployed summary app."
        ),
    )
    return parser.parse_args()


def choose_interactive_mode() -> tuple[str, str]:
    print("=" * 60)
    print("Capstone Reproducibility Pipeline")
    print("=" * 60)
    print("[1] paper     Reproduce final paper results")
    print("[2] summary   Open/read the summary app")
    print("[3] validate  Check frozen artifacts/design/exports")
    print("[4] rebuild   Optional upstream rebuild from raw dataset")
    print()

    choice = input("Select mode [1-4], or press Enter for paper: ").strip()

    mode_map = {
        "": "paper",
        "1": "paper",
        "2": "summary",
        "3": "validate",
        "4": "rebuild",
    }

    if choice not in mode_map:
        raise SystemExit(f"Invalid choice: {choice}")

    mode = mode_map[choice]
    summary_target = "local"

    if mode == "summary":
        print()
        print("[1] deployed  Open public deployed app")
        print("[2] local     Launch local Streamlit app from this repo")
        summary_choice = input("Select summary target [1-2], or press Enter for deployed: ").strip()
        if summary_choice in ("", "1"):
            summary_target = "deployed"
        elif summary_choice == "2":
            summary_target = "local"
        else:
            raise SystemExit(f"Invalid summary target: {summary_choice}")

    return mode, summary_target


def run_paper() -> None:
    from codes.pipelines.reproduce_paper import run_paper_reproduction

    print("=" * 72)
    print("MODE: PAPER REPRODUCTION")
    print("=" * 72)
    output = run_paper_reproduction()
    print()
    print(f"Paper outputs written to: {output}")


def run_validate() -> None:
    from codes.pipelines.validate_artifacts import validate_frozen_artifacts
    from codes.pipelines.validate_experiment_design import validate_experiment_design

    print("=" * 72)
    print("MODE: VALIDATION")
    print("=" * 72)

    print("[1/2] Frozen artifact integrity")
    result = validate_frozen_artifacts()
    print(
        "      OK: "
        f"final_cases={result.get('final_cases')}  "
        f"practice_cases={result.get('practice_cases')}  "
        f"candidate_pool_rows={result.get('candidate_pool_rows'):,}"
    )

    print("[2/2] Experiment design, platform sync, and export schema")
    validate_experiment_design()

    print()
    print("Validation passed.")


def run_summary(target: str = "local") -> None:
    print("=" * 72)
    print("MODE: SUMMARY APP")
    print("=" * 72)

    if target == "deployed":
        print(f"Opening deployed summary app: {DEPLOYED_SUMMARY_URL}")
        print("Note: this is for presentation/exploration; official reproduction is `python run.py`.")
        webbrowser.open(DEPLOYED_SUMMARY_URL)
        return

    from codes.pipelines.reproduce_paper import run_paper_reproduction

    print("[1/2] Regenerating paper outputs for local summary app")
    output = run_paper_reproduction()
    print(f"Paper outputs written to: {output}")

    print("[2/2] Launching local Streamlit summary app")
    print("      Local URL is usually http://localhost:8501")
    print(f"      Deployed URL: {DEPLOYED_SUMMARY_URL}")

    try:
        env = os.environ.copy()
        env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "codes/summary_app/app.py"],
            check=False,
            env=env,
        )
    except KeyboardInterrupt:
        print("\nSummary app stopped by user.")


def run_rebuild() -> None:
    print("=" * 72)
    print("MODE: OPTIONAL UPSTREAM REBUILD")
    print("=" * 72)
    print("This mode is provenance only. It is not the official paper reproduction path.")
    print("It requires data/raw/loan.csv.")
    print("It writes rebuilt upstream artifacts only under artifacts/build/.")
    print("It never modifies artifacts/frozen/, data/experiment_exports/, artifacts/tables/, or artifacts/figures/.\n")

    from codes.pipelines.rebuild_from_upstream import run_rebuild_from_upstream

    try:
        output = run_rebuild_from_upstream()
    except RuntimeError as exc:
        print("Rebuild could not run:")
        print(exc)
        return

    print(f"\nRebuilt upstream outputs written to: {output}")
    print("Frozen artifacts were not modified.")


def main() -> None:
    args = parse_args()

    if args.interactive:
        mode, summary_target = choose_interactive_mode()
    else:
        mode = args.mode
        summary_target = args.summary_target

    if mode == "paper":
        run_paper()
    elif mode == "summary":
        run_summary(target=summary_target)
    elif mode == "validate":
        run_validate()
    elif mode == "rebuild":
        run_rebuild()
    else:
        raise SystemExit(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()
