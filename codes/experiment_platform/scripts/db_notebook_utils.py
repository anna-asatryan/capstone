from __future__ import annotations

from pathlib import Path

import pandas as pd
import toml
from supabase import create_client


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_DIR.parent.parent
DEFAULT_EXPORT_DIR = REPO_ROOT / "data" / "experiment_exports"
SECRETS_PATH = PROJECT_DIR / ".streamlit" / "secrets.toml"


def load_client():
    secrets = toml.load(SECRETS_PATH)
    return create_client(
        secrets["supabase"]["url"],
        secrets["supabase"]["secret_key"],
    )


def fetch_table(client, table_name: str, page_size: int = 1000) -> pd.DataFrame:
    rows, offset = [], 0

    while True:
        response = (
            client
            .table(table_name)
            .select("*")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = response.data or []
        rows.extend(batch)

        if len(batch) < page_size:
            break

        offset += page_size

    return pd.DataFrame(rows)


def fetch_live_tables() -> dict[str, pd.DataFrame]:
    client = load_client()
    return {
        "participants": fetch_table(client, "participants"),
        "trials": fetch_table(client, "trials"),
        "quiz_responses": fetch_table(client, "quiz_responses"),
    }


def load_exported_tables(export_dir: str | Path = DEFAULT_EXPORT_DIR) -> dict[str, pd.DataFrame]:
    base = Path(export_dir)
    return {
        "participants": pd.read_csv(base / "participants.csv"),
        "trials": pd.read_csv(base / "trials.csv"),
        "quiz_responses": pd.read_csv(base / "quiz_responses.csv"),
    }


def build_joined_trials(
    participants: pd.DataFrame,
    trials: pd.DataFrame,
) -> pd.DataFrame:
    if participants.empty or trials.empty:
        return pd.DataFrame()

    participant_cols = [
        "id",
        "participant_number",
        "participant_group",
        "age_range",
        "education",
        "completed",
        "current_phase",
        "started_at",
        "completed_at",
        "trust_rating",
        "self_reported_reliance",
        "ai_surprise_strategy",
        "total_cost",
        "optimal_cost",
    ]

    available = [col for col in participant_cols if col in participants.columns]

    joined = trials.merge(
        participants[available],
        left_on="participant_id",
        right_on="id",
        how="left",
        suffixes=("", "_participant"),
    )

    if "trial_index" in joined.columns:
        joined["is_practice"] = joined["trial_index"] < 1
        joined["is_experimental"] = joined["trial_index"] >= 1
    else:
        joined["is_practice"] = False
        joined["is_experimental"] = False

    required_change_cols = {"decision_init", "decision_final"}
    if required_change_cols.issubset(joined.columns):
        joined["changed_mind"] = (
            joined["decision_init"].notna()
            & joined["decision_final"].notna()
            & (joined["decision_init"] != joined["decision_final"])
        )
    else:
        joined["changed_mind"] = False

    required_correct_cols = {"decision_final", "y_true"}
    if required_correct_cols.issubset(joined.columns):
        joined["final_correct"] = joined["decision_final"] == (1 - joined["y_true"])
    else:
        joined["final_correct"] = pd.NA

    return joined


def quiz_scores(quiz_responses: pd.DataFrame) -> pd.DataFrame:
    if quiz_responses.empty:
        return pd.DataFrame(columns=["participant_id", "attempt", "correct_answers"])

    return (
        quiz_responses
        .groupby(["participant_id", "attempt"], dropna=False)["is_correct"]
        .sum()
        .reset_index(name="correct_answers")
    )


def participant_status(participants: pd.DataFrame, trials: pd.DataFrame) -> pd.DataFrame:
    if participants.empty:
        return pd.DataFrame()

    trial_counts = (
        trials
        .groupby("participant_id", dropna=False)
        .size()
        .reset_index(name="trial_rows")
        if not trials.empty
        else pd.DataFrame(columns=["participant_id", "trial_rows"])
    )

    status = participants.merge(
        trial_counts,
        left_on="id",
        right_on="participant_id",
        how="left",
    )

    status["trial_rows"] = status["trial_rows"].fillna(0).astype(int)

    if "participant_number" in status.columns:
        return status.sort_values("participant_number")

    return status