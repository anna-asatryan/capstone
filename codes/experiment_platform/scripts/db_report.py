from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import toml
from supabase import create_client


PROJECT_DIR = Path(__file__).resolve().parents[1]
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
        response = client.table(table_name).select("*").range(offset, offset + page_size - 1).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return pd.DataFrame(rows)


def print_summary(participants: pd.DataFrame, trials: pd.DataFrame, quiz: pd.DataFrame) -> None:
    completed = int(participants["completed"].fillna(False).sum()) if not participants.empty else 0
    print("COUNTS")
    print(
        {
            "participants": int(len(participants)),
            "trials": int(len(trials)),
            "quiz_responses": int(len(quiz)),
            "completed_participants": completed,
        }
    )

    if not participants.empty:
        print("\nPARTICIPANT_PHASES")
        phase_summary = (
            participants.groupby(["current_phase", "completed"], dropna=False)
            .size()
            .reset_index(name="n")
        )
        print(phase_summary.to_string(index=False))

        print("\nPARTICIPANT_GROUPS")
        groups = participants.groupby("participant_group", dropna=False).size().reset_index(name="n")
        print(groups.to_string(index=False))

        print("\nMOST_RECENT_PARTICIPANTS")
        cols = [
            "participant_number",
            "participant_group",
            "current_phase",
            "current_trial_index",
            "completed",
            "started_at",
        ]
        available = [col for col in cols if col in participants.columns]
        recent = participants.sort_values("started_at", ascending=False)[available].head(10)
        print(recent.to_string(index=False))

    if not trials.empty:
        print("\nTRIALS_BY_PROTOCOL")
        by_protocol = trials.groupby("protocol", dropna=False).size().reset_index(name="n")
        print(by_protocol.to_string(index=False))

        print("\nTRIALS_BY_BLOCK")
        by_block = trials.groupby("block", dropna=False).size().reset_index(name="n")
        print(by_block.to_string(index=False))

        print("\nTRIAL_ROWS_PER_PARTICIPANT")
        per_participant = (
            trials.groupby("participant_id")
            .size()
            .reset_index(name="trial_rows")
            .sort_values("trial_rows", ascending=False)
        )
        print(per_participant.head(10).to_string(index=False))

        experimental = trials[trials["trial_index"] >= 1].copy()
        if not experimental.empty:
            print("\nEXPERIMENTAL_TRIALS_ONLY")
            protocol_summary = (
                experimental.groupby("protocol", dropna=False)
                .agg(
                    n=("protocol", "size"),
                    mean_total_ms=("total_trial_ms", "mean"),
                )
                .reset_index()
            )
            print(protocol_summary.to_string(index=False))

    if not quiz.empty:
        print("\nQUIZ_SCORES")
        quiz_scores = (
            quiz.groupby(["participant_id", "attempt"])["is_correct"]
            .sum()
            .reset_index(name="correct_answers")
        )
        print(quiz_scores.head(20).to_string(index=False))


def export_tables(export_dir: Path, participants: pd.DataFrame, trials: pd.DataFrame, quiz: pd.DataFrame) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)
    participants.to_csv(export_dir / "participants.csv", index=False)
    trials.to_csv(export_dir / "trials.csv", index=False)
    quiz.to_csv(export_dir / "quiz_responses.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Supabase audit and export utility.")
    parser.add_argument(
        "--export-dir",
        type=Path,
        help="Optional directory where participants/trials/quiz_responses CSVs will be exported.",
    )
    args = parser.parse_args()

    client = load_client()
    participants = fetch_table(client, "participants")
    trials = fetch_table(client, "trials")
    quiz = fetch_table(client, "quiz_responses")

    print_summary(participants, trials, quiz)

    if args.export_dir:
        export_tables(args.export_dir, participants, trials, quiz)
        print(f"\nExported CSVs to {args.export_dir}")


if __name__ == "__main__":
    main()
