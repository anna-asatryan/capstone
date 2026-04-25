#!/usr/bin/env python3
"""
Capstone reproducibility entrypoint.

    python run.py                   # reproduce final paper results (default)
    python run.py --mode paper      # same as above
    python run.py --mode summary    # launch summary visualisation app
    python run.py --mode validate   # integrity checks on all frozen artifacts
    python run.py --mode rebuild-design  # best-effort upstream rebuild (audit only)

The single-command reproducibility rule:
    `python run.py` reproduces the main paper results from frozen participant exports.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from codes.pipelines.common import ANALYSIS_DIR, ARTIFACTS_DIR, FROZEN_ARTIFACTS_DIR

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ARTIFACTS_DIR / "build"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capstone reproducibility entrypoint. "
            "Default: reproduce final paper results from frozen participant exports."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["paper", "summary", "validate", "rebuild-design"],
        default="paper",
        help=(
            "paper         : reproduce final paper results from frozen participant exports\n"
            "summary       : launch the summary visualisation app\n"
            "validate      : check integrity of all frozen artifacts\n"
            "rebuild-design: best-effort upstream design rebuild (writes to artifacts/build/ only)"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ANALYSIS_DIR,
        help="Directory where analysis outputs are written (default: artifacts/analysis/latest/).",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Mode: paper
# ---------------------------------------------------------------------------

def run_paper(output_dir: Path) -> Path:
    from codes.pipelines.reproduce_paper import run_paper_reproduction

    print("=" * 60)
    print("Paper reproduction mode")
    print("Loading frozen participant exports and frozen case design.")
    print("=" * 60)

    out = run_paper_reproduction(output_dir=output_dir.resolve())
    return out


# ---------------------------------------------------------------------------
# Mode: summary
# ---------------------------------------------------------------------------

def _launch_summary_app(data_dir: Path) -> int:
    command = [
        sys.executable,
        "-m",
        "codes.summary_app.app",
        "--data-dir",
        str(data_dir),
    ]
    return subprocess.run(command, cwd=ROOT).returncode


def run_summary(output_dir: Path) -> None:
    analysis_dir = output_dir.resolve()
    summary_json = analysis_dir / "summary.json"

    if not summary_json.exists():
        print(
            f"No analysis bundle found at {analysis_dir}.\n"
            "Running paper reproduction first...\n"
        )
        run_paper(analysis_dir)

    print(f"\nLaunching summary app from {analysis_dir} ...")
    raise SystemExit(_launch_summary_app(analysis_dir))


# ---------------------------------------------------------------------------
# Mode: validate
# ---------------------------------------------------------------------------

def run_validate() -> None:
    from codes.pipelines.validate_artifacts import validate_frozen_artifacts
    from codes.pipelines.validate_experiment_design import (
        validate_experiment_design,
        validate_participant_exports,
    )

    print("=" * 60)
    print("Validate mode")
    print("=" * 60)

    # 1. Frozen artifact integrity (hashes + required columns + counts)
    print("\n[1/3] Frozen artifact integrity...")
    result = validate_frozen_artifacts()
    print(
        f"      final_cases={result['final_cases']}  "
        f"practice_cases={result['practice_cases']}  "
        f"candidate_pool_rows={result['candidate_pool_rows']}"
    )

    # 2. Experiment design structure + platform CSV sync + config.py
    print("\n[2/3] Experiment design structure...")
    validate_experiment_design()

    # 3. Participant export schema (skipped gracefully if not yet collected)
    exports_dir = FROZEN_ARTIFACTS_DIR / "experiment_exports"
    if (exports_dir / "participants.csv").exists() or (exports_dir / "trials.csv").exists():
        print("\n[3/3] Participant export schema...")
        problems = validate_participant_exports(exports_dir)
        if problems:
            print("  PARTICIPANT EXPORT WARNINGS:")
            for p in problems:
                print(f"    {p}")
        else:
            print("  Participant export schema OK.")
    else:
        print(
            f"\n[3/3] Participant exports not found at {exports_dir} — "
            "skipping (pre-data-collection)."
        )

    print("\nAll validation checks passed.")


# ---------------------------------------------------------------------------
# Mode: rebuild-design
# ---------------------------------------------------------------------------

def run_rebuild_design(output_dir: Path) -> Path:
    from codes.pipelines.rebuild_from_upstream import run_rebuild_from_upstream

    print("=" * 60)
    print("Rebuild-design mode  [AUDIT / PROVENANCE ONLY]")
    print()
    print("This is NOT the official paper reproduction path.")
    print("Outputs go to artifacts/build/ only.")
    print("artifacts/frozen/ is never modified.")
    print("=" * 60)
    print()

    out = run_rebuild_from_upstream(
        analysis_output_dir=output_dir.resolve(),
        rebuild_artifacts_dir=BUILD_DIR,
    )
    print(
        "\nRebuild completed. Do not use rebuilt outputs as official results.\n"
        "Run 'python run.py --mode validate' to confirm frozen artifacts are intact."
    )
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Interactive menu if no arguments provided
    if len(sys.argv) == 1:
        print("=" * 60)
        print("Capstone Reproducibility Pipeline")
        print("=" * 60)
        print("Select a mode to run:")
        print("  [1] paper          (default) reproduce final paper results")
        print("  [2] summary        launch summary visualisation app")
        print("  [3] validate       check integrity of all frozen artifacts")
        print("  [4] rebuild-design best-effort upstream design rebuild (audit only)")
        print()
        
        try:
            choice = input("Enter choice [1-4] or press Enter for default [1]: ").strip()
        except KeyboardInterrupt:
            print("\nExiting.")
            sys.exit(1)
            
        mode_map = {
            "": "paper",
            "1": "paper",
            "2": "summary",
            "3": "validate",
            "4": "rebuild-design",
        }
        
        mode = mode_map.get(choice)
        if not mode:
            print(f"\nInvalid choice '{choice}'. Exiting.")
            sys.exit(1)
            
        sys.argv.extend(["--mode", mode])

    args = parse_args()
    output_dir: Path = args.output_dir

    if args.mode == "paper":
        out = run_paper(output_dir)
        print(f"\nOutputs written to: {out}")

    elif args.mode == "summary":
        run_summary(output_dir)  # raises SystemExit

    elif args.mode == "validate":
        run_validate()

    elif args.mode == "rebuild-design":
        out = run_rebuild_design(output_dir)
        print(f"\nRebuild analysis outputs written to: {out}")


if __name__ == "__main__":
    main()
