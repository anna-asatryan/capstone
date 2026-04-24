from __future__ import annotations

import argparse
from pathlib import Path

from codes.pipelines.common import ANALYSIS_DIR, FROZEN_ARTIFACTS_DIR, write_analysis_outputs
from codes.pipelines.validate_artifacts import validate_frozen_artifacts
from codes.pipelines.common import load_frozen_tables


def run_reproduction_from_frozen(output_dir: Path | None = None) -> Path:
    validate_frozen_artifacts(FROZEN_ARTIFACTS_DIR)
    tables = load_frozen_tables(FROZEN_ARTIFACTS_DIR)
    experiment_exports_dir = FROZEN_ARTIFACTS_DIR / "experiment_exports"
    return write_analysis_outputs(
        mode="frozen",
        final_cases=tables["final_cases"],
        practice_cases=tables["practice_cases"],
        candidate_pool=tables["candidate_pool"],
        protocol_rotation=tables["protocol_rotation"],
        manifest=tables["manifest"],
        warnings=[],
        output_dir=output_dir or ANALYSIS_DIR,
        experiment_exports_dir=experiment_exports_dir,
        exact_case_match=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic frozen reproduction path.")
    parser.add_argument(
        "--output-dir",
        default=str(ANALYSIS_DIR),
        help="Directory where downstream analysis outputs should be written.",
    )
    args = parser.parse_args()

    output_dir = run_reproduction_from_frozen(Path(args.output_dir))
    print(f"Frozen reproduction outputs written to {output_dir}")


if __name__ == "__main__":
    main()
