from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st

from metrics import TAU, trial_cost


@dataclass(frozen=True)
class AppData:
    root: Path
    participants_raw: pd.DataFrame
    trials_raw: pd.DataFrame
    quiz_raw: pd.DataFrame
    cases: pd.DataFrame
    trials: pd.DataFrame
    completed_ids: set
    warnings: list[str]


def find_repo_root(start: Optional[Path] = None) -> Path:
    start = start or Path(__file__).resolve()
    candidates = [start] + list(start.parents)
    for c in candidates:
        if (c / "artifacts").exists():
            return c
    # app.py is usually capstone/codes/summary_app/app.py, so parents[2] is capstone
    return Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def _case_id_fallback(trials: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    if "case_id" in trials.columns and trials["case_id"].notna().any():
        return trials
    # Fallback only for visualization. Do not claim true case-level inference if this is used.
    if "case_position" in trials.columns:
        trials["case_id"] = trials["case_position"].astype(str)
        warnings.append("No stable case_id column found; using case_position as a visualization fallback.")
    elif "trial_index" in trials.columns:
        trials["case_id"] = trials["trial_index"].astype(str)
        warnings.append("No stable case_id column found; using trial_index as a visualization fallback.")
    else:
        trials["case_id"] = np.arange(len(trials)).astype(str)
        warnings.append("No case identifier found; generated row-level IDs. Case explorer will be limited.")
    return trials


@st.cache_data(show_spinner=False)
def load_data(root_str: Optional[str] = None) -> AppData:
    root = Path(root_str) if root_str else find_repo_root()
    warnings: list[str] = []

    APP_DIR = Path(__file__).resolve().parent
    APP_DATA = APP_DIR / "data"

    if (APP_DATA / "participants.csv").exists() and (APP_DATA / "trials.csv").exists():
        participants = _read_csv(APP_DATA / "participants.csv")
        trials = _read_csv(APP_DATA / "trials.csv")
        quiz = _read_csv(APP_DATA / "quiz_responses.csv")
        cases = _read_csv(APP_DATA / "final_cases.csv")
    else:
        exports = root / "artifacts" / "db_exports"
        analysis_tables = root / "artifacts" / "analysis" / "tables"
        frozen = root / "artifacts" / "frozen"
        build = root / "artifacts" / "build"

        participants = _read_csv(exports / "participants.csv")
        trials = _read_csv(exports / "trials.csv")
        quiz = _read_csv(exports / "quiz_responses.csv")
        cases = _read_csv(frozen / "final_cases.csv")
        if cases.empty:
            cases = _read_csv(build / "final_cases.csv")

    if participants.empty or trials.empty:
        warnings.append("Could not find participants.csv or trials.csv under summary_app/data/ or artifacts/db_exports/.")
        return AppData(root, participants, trials, quiz, cases, trials, set(), warnings)

    # Probability scale guard.
    if "prob_estimate_final" in trials.columns:
        max_prob = trials["prob_estimate_final"].dropna().max()
        if pd.notna(max_prob) and max_prob > 1:
            for col in ["prob_estimate_final", "prob_estimate_init"]:
                if col in trials.columns:
                    trials[col] = trials[col] / 100.0
            warnings.append("Probability estimates appeared to be 0–100 scale and were divided by 100.")

    comp_mask = participants["completed"].fillna(False).astype(bool) if "completed" in participants else pd.Series(False, index=participants.index)
    completed_ids = set(participants.loc[comp_mask, "id"].astype(str)) if "id" in participants else set()

    trials = trials.copy()
    if "participant_id" in trials.columns:
        trials["participant_id"] = trials["participant_id"].astype(str)
        scored = trials[trials["participant_id"].isin(completed_ids)].copy()
    else:
        scored = trials.copy()
        warnings.append("trials.csv has no participant_id column; participant-level views are limited.")

    if "trial_index" in scored.columns:
        scored = scored[scored["trial_index"] >= 1].copy()

    # Merge participant group.
    if "participant_group" not in scored.columns and {"id", "participant_group"}.issubset(participants.columns):
        group_map = participants.set_index(participants["id"].astype(str))["participant_group"]
        scored["participant_group"] = scored["participant_id"].map(group_map)

    # Block order.
    if "block_order" not in scored.columns:
        if "block" in scored.columns:
            block_map = {"block_1": 1, "block_2": 2, "block_3": 3, 1: 1, 2: 2, 3: 3}
            scored["block_order"] = scored["block"].map(block_map)
        else:
            scored["block_order"] = np.nan

    # Case identifier and optional case metadata.
    scored = _case_id_fallback(scored, warnings)
    if not cases.empty:
        # Normalize case_id merge if possible; avoid duplicate columns for fields already present.
        if "case_id" in cases.columns:
            cases = cases.copy()
            cases["case_id"] = cases["case_id"].astype(str)
            scored["case_id"] = scored["case_id"].astype(str)
            keep_cols = [c for c in cases.columns if c == "case_id" or c not in scored.columns]
            try:
                scored = scored.merge(cases[keep_cols], on="case_id", how="left", suffixes=("", "_case"))
            except Exception:
                warnings.append("Could not merge final_cases.csv onto trial data; case explorer uses trial fields only.")

    # Required behavioral variables.
    for col in ["decision_final", "y_true", "pred_prob", "prob_estimate_final"]:
        if col not in scored.columns:
            scored[col] = np.nan
            warnings.append(f"Missing expected column: {col}")

    scored["correct"] = (
        ((scored["decision_final"] == 1) & (scored["y_true"] == 0))
        | ((scored["decision_final"] == 0) & (scored["y_true"] == 1))
    ).astype(int)

    scored["trial_cost"] = [
        trial_cost(d, y) if pd.notna(d) and pd.notna(y) else np.nan
        for d, y in zip(scored["decision_final"], scored["y_true"])
    ]
    scored["optimal_dec"] = (scored["pred_prob"] < TAU).astype(int)
    scored["opt_cost"] = [
        trial_cost(d, y) if pd.notna(d) and pd.notna(y) else np.nan
        for d, y in zip(scored["optimal_dec"], scored["y_true"])
    ]
    scored["cost_excess"] = scored["trial_cost"] - scored["opt_cost"]
    scored["prob_dist"] = (scored["prob_estimate_final"] - scored["pred_prob"]).abs()

    scored["ai_rec"] = (scored["pred_prob"] < TAU).astype(int)
    scored["follows_ai"] = (scored["decision_final"] == scored["ai_rec"]).astype(int)
    scored["ai_correct"] = (
        ((scored["ai_rec"] == 1) & (scored["y_true"] == 0))
        | ((scored["ai_rec"] == 0) & (scored["y_true"] == 1))
    ).astype(int)

    if "prob_estimate_init" in scored.columns:
        denom = scored["pred_prob"] - scored["prob_estimate_init"]
        scored["woa"] = np.where(
            denom.abs() >= 0.01,
            ((scored["prob_estimate_final"] - scored["prob_estimate_init"]) / denom).clip(-1, 2),
            np.nan,
        )
    else:
        scored["woa"] = np.nan
        warnings.append("No prob_estimate_init column found; WOA views unavailable.")

    # Stable ordering for difficulty.
    if "difficulty_tier" in scored.columns:
        scored["difficulty_tier"] = pd.Categorical(scored["difficulty_tier"], categories=["easy", "medium", "hard"], ordered=True)

    return AppData(root, participants, trials, quiz, cases, scored, completed_ids, warnings)
