from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from codes.pipelines.common import (
    FROZEN_ARTIFACTS_DIR,
    OFFICIAL_FROZEN_FILES,
    REQUIRED_CASE_COLUMNS,
    REQUIRED_POOL_COLUMNS,
    load_frozen_tables,
    read_json,
    sha256_file,
)


def validate_frozen_artifacts(base_dir: Path = FROZEN_ARTIFACTS_DIR) -> dict:
    missing = [name for name in OFFICIAL_FROZEN_FILES if not (base_dir / name).exists()]
    if missing:
        missing_display = ", ".join(sorted(missing))
        raise RuntimeError(
            f"Official frozen artifacts are missing from {base_dir}: {missing_display}"
        )

    lock = read_json(base_dir / "cases.lock.json")
    locked_files = lock.get("files", {})
    if not locked_files:
        raise RuntimeError("cases.lock.json is present but does not define any locked files.")

    for relative_name, expected in locked_files.items():
        path = base_dir / relative_name
        if not path.exists():
            raise RuntimeError(f"Locked artifact is missing: {path}")
        actual_hash = sha256_file(path)
        if actual_hash != expected.get("sha256"):
            raise RuntimeError(
                f"Hash mismatch for {relative_name}: expected {expected.get('sha256')}, got {actual_hash}"
            )

    tables = load_frozen_tables(base_dir)
    final_cases = tables["final_cases"]
    practice_cases = tables["practice_cases"]
    protocol_rotation = tables["protocol_rotation"]
    candidate_pool = tables["candidate_pool"]
    manifest = tables["manifest"]

    missing_case_columns = [col for col in REQUIRED_CASE_COLUMNS if col not in final_cases.columns]
    missing_pool_columns = [col for col in REQUIRED_POOL_COLUMNS if col not in candidate_pool.columns]
    if missing_case_columns:
        raise RuntimeError(
            "final_cases.csv is missing required columns: "
            + ", ".join(sorted(missing_case_columns))
        )
    if missing_pool_columns:
        raise RuntimeError(
            "candidate_pool_scored.parquet is missing required columns: "
            + ", ".join(sorted(missing_pool_columns))
        )

    if len(final_cases) != 18:
        raise RuntimeError(f"Expected 18 final cases, found {len(final_cases)}.")
    if len(practice_cases) != 2:
        raise RuntimeError(f"Expected 2 practice cases, found {len(practice_cases)}.")
    if protocol_rotation.shape[0] != 3:
        raise RuntimeError(
            f"Expected 3 rows in protocol_rotation.csv, found {protocol_rotation.shape[0]}."
        )
    if candidate_pool.empty:
        raise RuntimeError("candidate_pool_scored.parquet is empty.")

    manifest_hashes = manifest.get("artifacts", {})
    for relative_name, metadata in manifest_hashes.items():
        path = base_dir / relative_name
        if not path.exists():
            raise RuntimeError(f"Manifest references a missing artifact: {relative_name}")
        actual_hash = sha256_file(path)
        if actual_hash != metadata.get("sha256"):
            raise RuntimeError(
                f"Manifest hash mismatch for {relative_name}: expected {metadata.get('sha256')}, got {actual_hash}"
            )

    return {
        "base_dir": str(base_dir),
        "final_cases": len(final_cases),
        "practice_cases": len(practice_cases),
        "candidate_pool_rows": len(candidate_pool),
        "manifest_version": manifest.get("version"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate official frozen reproduction artifacts.")
    parser.add_argument(
        "--base-dir",
        default=str(FROZEN_ARTIFACTS_DIR),
        help="Directory containing the official frozen artifacts.",
    )
    args = parser.parse_args()

    result = validate_frozen_artifacts(Path(args.base_dir))
    print("Frozen artifacts validated successfully.")
    print(
        f"final_cases={result['final_cases']} practice_cases={result['practice_cases']} "
        f"candidate_pool_rows={result['candidate_pool_rows']}"
    )


if __name__ == "__main__":
    main()
