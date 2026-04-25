from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from codes.pipelines.common import ANALYSIS_DIR

# Tables produced by reproduce_paper.py — absent when no participant data yet
PARTICIPANT_TABLES = [
    "hypothesis_summary",
    "protocol_outcomes",
    "reliance_summary",
    "revision_paths",
    "case_level_summary",
    "calibration_by_protocol",
    "participants_clean",
    "trials_clean",
]

# Tables always produced by write_analysis_outputs (design artifacts)
DESIGN_TABLES = [
    "model_metrics",
    "calibration_bins",
    "difficulty_summary",
    "selection_cells",
    "case_costs",
    "protocol_design",
    "final_cases",
    "practice_cases",
    "protocol_rotation",
]

# Optional tables written by extended statistical analysis
OPTIONAL_TABLES = [
    "mixed_effects_results",
    "exclusion_summary",
    "cost_benchmarks",
]


def resolve_data_dir(data_dir: str | Path | None = None) -> Path:
    return Path(data_dir) if data_dir else ANALYSIS_DIR


def _load_table(data_dir: Path, name: str) -> pd.DataFrame | None:
    path = data_dir / "tables" / f"{name}.csv"
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def load_analysis_bundle(data_dir: str | Path | None = None) -> dict[str, Any]:
    resolved = resolve_data_dir(data_dir)
    summary_path = resolved / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(
            f"No analysis bundle found at {summary_path}.\n"
            "Run `python run.py` to generate analysis outputs first."
        )

    summary = json.loads(summary_path.read_text())
    all_names = PARTICIPANT_TABLES + DESIGN_TABLES + OPTIONAL_TABLES
    tables = {name: _load_table(resolved, name) for name in all_names}

    has_participant_data = tables.get("trials_clean") is not None

    return {
        "data_dir": resolved,
        "summary": summary,
        "tables": tables,
        "has_participant_data": has_participant_data,
    }
