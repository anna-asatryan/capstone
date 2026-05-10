"""
Structural validation of the frozen experiment design and (optionally) participant exports.

Checks beyond validate_artifacts.py:
  - frozen artifact CSVs exist in artifacts/frozen/
  - platform package CSVs exist in codes/experiment_platform/data/frozen/
  - platform package CSVs match artifacts/frozen/ (byte-for-byte)
  - 3 blocks × 6 cases each
  - exactly 3 cases per difficulty × correctness cell
  - no practice/experimental case_id overlap
  - protocol rotation has correct groups and protocols
  - config.py loads successfully
  - config.py case IDs match frozen CSV exactly

If artifacts/db_exports/ exists, also validates:
  - required participant and trial columns are present
  - human_first init columns present when human_first trials exist
  - completed participants have 18 scored trials each

Usage:
    python3 -m codes.pipelines.validate_experiment_design
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import sys
from pathlib import Path

import pandas as pd

from codes.pipelines.common import ARTIFACTS_DIR, FROZEN_ARTIFACTS_DIR
from codes.pipelines.reproduce_paper import (
    REQUIRED_PARTICIPANT_COLS,
    REQUIRED_TRIAL_COLS,
    _SCORED_BLOCKS,
)

_ROOT = Path(__file__).resolve().parents[2]
_PLATFORM_FROZEN_DIR = _ROOT / "codes" / "experiment_platform" / "data" / "frozen"
_PLATFORM_DIR = _ROOT / "codes" / "experiment_platform"

_CSV_FILES = ["final_cases.csv", "practice_cases.csv", "protocol_rotation.csv"]
_EXPECTED_BLOCKS = {"block_1", "block_2", "block_3"}
_EXPECTED_GROUPS = {"group_1", "group_2", "group_3"}
_EXPECTED_PROTOCOLS = {"no_ai", "human_first", "ai_first"}


def _sha256(path: Path) -> str:
    d = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            d.update(chunk)
    return d.hexdigest()


def validate_experiment_design(frozen_dir: Path = FROZEN_ARTIFACTS_DIR) -> None:
    errors: list[str] = []

    # ------------------------------------------------------------------
    # 1. Frozen artifact CSVs exist
    # ------------------------------------------------------------------
    for name in _CSV_FILES:
        if not (frozen_dir / name).exists():
            errors.append(f"Missing frozen artifact: {frozen_dir / name}")

    # ------------------------------------------------------------------
    # 2. Platform package CSVs exist
    # ------------------------------------------------------------------
    for name in _CSV_FILES:
        if not (_PLATFORM_FROZEN_DIR / name).exists():
            errors.append(f"Missing platform CSV: {_PLATFORM_FROZEN_DIR / name}")

    if errors:
        _report(errors)

    # ------------------------------------------------------------------
    # 3. Platform CSVs match artifacts/frozen/ byte-for-byte
    # ------------------------------------------------------------------
    for name in _CSV_FILES:
        h_frozen = _sha256(frozen_dir / name)
        h_platform = _sha256(_PLATFORM_FROZEN_DIR / name)
        if h_frozen != h_platform:
            errors.append(
                f"{name} mismatch between artifacts/frozen/ and platform data/frozen/\n"
                f"  artifacts/frozen : {h_frozen}\n"
                f"  platform data    : {h_platform}"
            )

    # ------------------------------------------------------------------
    # 4. Structural checks
    # ------------------------------------------------------------------
    fc = pd.read_csv(frozen_dir / "final_cases.csv")
    pc = pd.read_csv(frozen_dir / "practice_cases.csv")
    pr = pd.read_csv(frozen_dir / "protocol_rotation.csv")

    if len(fc) != 18:
        errors.append(f"Expected 18 final cases, got {len(fc)}")

    if len(pc) != 2:
        errors.append(f"Expected 2 practice cases, got {len(pc)}")

    overlap = set(fc["case_id"]) & set(pc["case_id"])
    if overlap:
        errors.append(f"Practice/experimental case_id overlap: {overlap}")

    block_counts = fc.groupby("block")["case_id"].count()
    if set(block_counts.index) != _EXPECTED_BLOCKS:
        errors.append(f"Wrong blocks: {set(block_counts.index)}")
    elif not (block_counts == 6).all():
        errors.append(f"Block case counts not all 6: {block_counts.to_dict()}")

    cell_counts = fc.groupby(["difficulty_tier", "correct"])["case_id"].count()
    bad_cells = cell_counts[cell_counts != 3]
    if not bad_cells.empty:
        errors.append(f"Cell counts not all 3:\n{bad_cells}")

    if set(pr["participant_group"]) != _EXPECTED_GROUPS:
        errors.append(f"Wrong protocol groups: {set(pr['participant_group'])}")

    for _, row in pr.iterrows():
        protos = {row["block_1_protocol"], row["block_2_protocol"], row["block_3_protocol"]}
        if protos != _EXPECTED_PROTOCOLS:
            errors.append(f"{row['participant_group']} missing protocol(s): {protos}")

    # ------------------------------------------------------------------
    # 5. config.py loads and IDs match
    # ------------------------------------------------------------------
    try:
        if str(_PLATFORM_DIR) not in sys.path:
            sys.path.insert(0, str(_PLATFORM_DIR))
        if "config" in sys.modules:
            importlib.reload(sys.modules["config"])
        else:
            import importlib as _il
            _il.import_module("config")
        import config  # type: ignore[import]

        config_ids = sorted(c["case_id"] for c in config.EXPERIMENTAL_CASES)
        frozen_ids = sorted(fc["case_id"].tolist())
        if config_ids != frozen_ids:
            errors.append(
                f"config.py experimental IDs don't match frozen CSV.\n"
                f"  config: {config_ids}\n  frozen: {frozen_ids}"
            )

        config_practice_ids = sorted(c["case_id"] for c in config.PRACTICE_CASES)
        frozen_practice_ids = sorted(pc["case_id"].tolist())
        if config_practice_ids != frozen_practice_ids:
            errors.append(
                f"config.py practice IDs don't match frozen CSV.\n"
                f"  config: {config_practice_ids}\n  frozen: {frozen_practice_ids}"
            )
    except Exception as exc:
        errors.append(f"Could not import config.py: {exc}")

    # ------------------------------------------------------------------
    # 6. Participant exports (optional — skip if not yet collected)
    # ------------------------------------------------------------------
    export_problems = validate_participant_exports()
    if export_problems:
        for p in export_problems:
            errors.append(f"[participant exports] {p}")

    _report(errors, fc=fc, pc=pc, pr=pr, block_counts=block_counts)


def validate_participant_exports(
    exports_dir: Path | None = None,
) -> list[str]:
    """
    Validate participant export schema and structural integrity.

    Returns a list of problems (empty = OK).
    Does not raise — caller decides how to handle warnings vs errors.
    If exports_dir doesn't exist or has no CSVs, returns [] (pre-data-collection is fine).
    """
    exp_dir = exports_dir or (ARTIFACTS_DIR / "db_exports")
    participants_path = exp_dir / "participants.csv"
    trials_path = exp_dir / "trials.csv"

    if not participants_path.exists() and not trials_path.exists():
        return []

    problems: list[str] = []

    if not participants_path.exists():
        problems.append(f"participants.csv missing from {exp_dir}")
        return problems
    if not trials_path.exists():
        problems.append(f"trials.csv missing from {exp_dir}")
        return problems

    participants = pd.read_csv(participants_path)
    trials = pd.read_csv(trials_path)

    missing_p = REQUIRED_PARTICIPANT_COLS - set(participants.columns)
    if missing_p:
        problems.append(f"participants.csv missing required columns: {sorted(missing_p)}")

    missing_t = REQUIRED_TRIAL_COLS - set(trials.columns)
    if missing_t:
        problems.append(f"trials.csv missing required columns: {sorted(missing_t)}")

    if "protocol" in trials.columns:
        hf = trials[trials["protocol"] == "human_first"]
        if not hf.empty:
            for col in ("decision_init", "prob_estimate_init"):
                if col not in trials.columns:
                    problems.append(
                        f"human_first trials exist but '{col}' absent from trials.csv"
                    )

    if "completed" in participants.columns and "participant_id" in trials.columns:
        completed_ids = set(
            participants[participants["completed"].astype(bool)]["id"]
        )
        for pid in completed_ids:
            scored = trials[
                (trials["participant_id"] == pid)
                & (trials["block"].isin(_SCORED_BLOCKS))
            ]
            if len(scored) != 18:
                problems.append(
                    f"Participant {pid}: expected 18 scored trials, found {len(scored)}"
                )

    return problems


def _report(
    errors: list[str],
    fc: "pd.DataFrame | None" = None,
    pc: "pd.DataFrame | None" = None,
    pr: "pd.DataFrame | None" = None,
    block_counts: "pd.Series | None" = None,
) -> None:
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    block_counts_str = (
        ", ".join(f"{b}={n}" for b, n in sorted(block_counts.items()))
        if block_counts is not None
        else "n/a"
    )
    print("Experiment design validated successfully.")
    print(f"  final_cases=18  practice_cases=2  no_id_overlap=True")
    print(f"  blocks: {block_counts_str}")
    print(f"  difficulty×correct cells: all 6 cells have exactly 3 cases")
    if pr is not None:
        print(f"  protocol groups: {sorted(pr['participant_group'].tolist())}")
    print(f"  platform CSVs match artifacts/frozen/ (byte-for-byte)")
    print(f"  config.py IDs match frozen CSV")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate frozen experiment design structure.")
    parser.add_argument(
        "--frozen-dir",
        default=str(FROZEN_ARTIFACTS_DIR),
        help="Directory containing the official frozen artifacts.",
    )
    args = parser.parse_args()
    validate_experiment_design(Path(args.frozen_dir))


if __name__ == "__main__":
    main()
