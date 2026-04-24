from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from codes.pipelines.common import ANALYSIS_DIR


def resolve_data_dir(data_dir: str | Path | None = None) -> Path:
    return Path(data_dir) if data_dir else ANALYSIS_DIR


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_table(data_dir: Path, name: str) -> pd.DataFrame | None:
    path = data_dir / "tables" / f"{name}.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


def load_analysis_bundle(data_dir: str | Path | None = None) -> dict[str, Any]:
    resolved = resolve_data_dir(data_dir)
    summary_path = resolved / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(
            f"No analysis bundle found at {summary_path}. Run the reproduction pipeline first."
        )

    table_names = [
        "model_metrics",
        "calibration_bins",
        "difficulty_summary",
        "selection_cells",
        "case_costs",
        "protocol_design",
        "final_cases",
        "practice_cases",
        "participant_protocol_summary",
        "participant_reliance_summary",
    ]
    tables = {name: load_table(resolved, name) for name in table_names}
    return {"data_dir": resolved, "summary": load_json(summary_path), "tables": tables}
