from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
FROZEN_ARTIFACTS_DIR = ARTIFACTS_DIR / "frozen"
ANALYSIS_DIR = ARTIFACTS_DIR / "analysis" / "latest"
REBUILD_DIR = ARTIFACTS_DIR / "rebuild"
DATA_DIR = ROOT_DIR / "data"

OFFICIAL_FROZEN_FILES = [
    "final_cases.csv",
    "practice_cases.csv",
    "protocol_rotation.csv",
    "candidate_pool_scored.parquet",
    "selection_manifest.json",
    "cases.lock.json",
]

REQUIRED_POOL_COLUMNS = [
    "case_id",
    "loan_amnt",
    "term",
    "int_rate",
    "dti",
    "revol_util",
    "home_ownership",
    "purpose",
    "log_annual_inc",
    "credit_history_years",
    "y_true",
    "pred_prob",
    "difficulty_score",
    "difficulty_tier",
]

REQUIRED_CASE_COLUMNS = [
    "case_id",
    "case_position",
    "block",
    "pred_prob",
    "y_true",
    "difficulty_tier",
    "difficulty_score",
]

C_FN = 5000
C_FP = 1000
TAU = C_FP / (C_FP + C_FN)


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit_hash() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def enrich_candidate_pool(df: pd.DataFrame) -> pd.DataFrame:
    enriched = df.copy()
    enriched["pred_prob"] = enriched["pred_prob"].clip(1e-6, 1 - 1e-6)
    enriched["model_pred_class"] = (enriched["pred_prob"] >= 0.5).astype(int)
    enriched["correct"] = (enriched["model_pred_class"] == enriched["y_true"]).astype(int)
    enriched["confidence"] = enriched["pred_prob"].where(
        enriched["pred_prob"] >= 0.5,
        1 - enriched["pred_prob"],
    )
    enriched["fp"] = (
        (enriched["model_pred_class"] == 1) & (enriched["y_true"] == 0)
    ).astype(int)
    enriched["fn"] = (
        (enriched["model_pred_class"] == 0) & (enriched["y_true"] == 1)
    ).astype(int)
    enriched["model_decision"] = (enriched["pred_prob"] < 0.5).astype(int)
    enriched["optimal_decision"] = (enriched["pred_prob"] < TAU).astype(int)
    enriched["model_optimal"] = (
        enriched["model_decision"] == enriched["optimal_decision"]
    ).astype(int)
    if "conf_bin" not in enriched.columns or enriched["conf_bin"].isna().any():
        def assign_conf_bin(values: pd.Series) -> pd.Series:
            if len(values) < 2 or values.nunique() < 2:
                return pd.Series(["low"] * len(values), index=values.index)
            ranked = values.rank(method="first")
            bins = pd.qcut(ranked, q=2, labels=["low", "high"], duplicates="drop")
            if getattr(bins, "nunique", lambda: 0)() == 1:
                return pd.Series(["low"] * len(values), index=values.index)
            return pd.Series(bins.astype(str), index=values.index)

        enriched["conf_bin"] = (
            enriched.groupby("difficulty_tier", observed=True)["confidence"]
            .transform(assign_conf_bin)
            .astype(str)
        )
    else:
        enriched["conf_bin"] = enriched["conf_bin"].astype(str)
    return enriched


def load_frozen_tables(base_dir: Path = FROZEN_ARTIFACTS_DIR) -> dict[str, Any]:
    final_cases = pd.read_csv(base_dir / "final_cases.csv")
    practice_cases = pd.read_csv(base_dir / "practice_cases.csv")
    protocol_rotation = pd.read_csv(base_dir / "protocol_rotation.csv")
    candidate_pool = pd.read_parquet(base_dir / "candidate_pool_scored.parquet")
    manifest = read_json(base_dir / "selection_manifest.json")
    return {
        "final_cases": enrich_candidate_pool(final_cases),
        "practice_cases": enrich_candidate_pool(practice_cases),
        "protocol_rotation": protocol_rotation,
        "candidate_pool": enrich_candidate_pool(candidate_pool),
        "manifest": manifest,
        "base_dir": base_dir,
    }


def compute_ece(y_true: pd.Series | list[float], y_prob: pd.Series | list[float], n_bins: int = 10) -> float:
    y_true_series = pd.Series(y_true, dtype="float64")
    y_prob_series = pd.Series(y_prob, dtype="float64").clip(1e-6, 1 - 1e-6)
    bins = pd.interval_range(start=0.0, end=1.0, periods=n_bins)
    bucketed = pd.cut(y_prob_series, bins=bins)
    working = pd.DataFrame(
        {"y_true": y_true_series, "y_prob": y_prob_series, "bucket": bucketed}
    ).dropna()
    if working.empty:
        return 0.0

    grouped = working.groupby("bucket", observed=True)
    ece = 0.0
    total = float(len(working))
    for _, group in grouped:
        weight = len(group) / total
        ece += weight * abs(group["y_true"].mean() - group["y_prob"].mean())
    return float(ece)


def trial_cost(decision: int, y_true: int, c_fn: int = C_FN, c_fp: int = C_FP) -> int:
    if decision == 1 and y_true == 1:
        return c_fn
    if decision == 0 and y_true == 0:
        return c_fp
    return 0


def load_experiment_export_summary(experiment_exports_dir: Path) -> dict[str, Any] | None:
    participants_path = experiment_exports_dir / "participants.csv"
    trials_path = experiment_exports_dir / "trials.csv"
    if not participants_path.exists() or not trials_path.exists():
        return None

    participants = pd.read_csv(participants_path)
    trials = pd.read_csv(trials_path)

    summary: dict[str, Any] = {
        "completed_participants": int(
            participants.get("completed", pd.Series(dtype="bool")).fillna(False).sum()
        )
        if "completed" in participants.columns
        else int(len(participants)),
        "trial_rows": int(len(trials)),
    }

    tables: dict[str, pd.DataFrame] = {}
    notes: list[str] = []

    if {"protocol", "decision_final", "y_true"}.issubset(trials.columns):
        protocol_df = trials.copy()
        protocol_df["correct_final"] = (
            protocol_df["decision_final"] != protocol_df["y_true"]
        ).astype(int)
        protocol_df["trial_cost"] = protocol_df.apply(
            lambda row: trial_cost(int(row["decision_final"]), int(row["y_true"])),
            axis=1,
        )
        tables["participant_protocol_summary"] = (
            protocol_df.groupby("protocol", observed=True)
            .agg(
                trials=("protocol", "size"),
                mean_accuracy=("correct_final", "mean"),
                mean_cost=("trial_cost", "mean"),
            )
            .reset_index()
        )
    else:
        notes.append(
            "Participant trials export is present, but it does not include the columns needed for protocol-level accuracy/cost summaries."
        )

    if {"protocol", "decision_init", "decision_final"}.issubset(trials.columns):
        human_first = trials[trials["protocol"] == "human_first"].copy()
        if not human_first.empty:
            human_first["changed_mind"] = (
                human_first["decision_init"] != human_first["decision_final"]
            ).astype(int)
            tables["participant_reliance_summary"] = (
                human_first.groupby("protocol", observed=True)
                .agg(
                    trials=("protocol", "size"),
                    revision_rate=("changed_mind", "mean"),
                )
                .reset_index()
            )
    else:
        notes.append(
            "Reliance summaries need `decision_init` and `decision_final` columns in the frozen trial export."
        )

    return {"summary": summary, "tables": tables, "notes": notes}


def model_metrics_table(candidate_pool: pd.DataFrame) -> pd.DataFrame:
    metrics = {
        "auc": roc_auc(candidate_pool["y_true"], candidate_pool["pred_prob"]),
        "brier": brier_score(candidate_pool["y_true"], candidate_pool["pred_prob"]),
        "log_loss": log_loss_score(candidate_pool["y_true"], candidate_pool["pred_prob"]),
        "ece": compute_ece(candidate_pool["y_true"], candidate_pool["pred_prob"]),
        "default_rate": float(candidate_pool["y_true"].mean()),
        "mean_pred_prob": float(candidate_pool["pred_prob"].mean()),
        "approval_rate_at_tau": float((candidate_pool["pred_prob"] < TAU).mean()),
        "approval_rate_at_0_5": float((candidate_pool["pred_prob"] < 0.5).mean()),
    }
    return pd.DataFrame(
        [{"metric": key, "value": round(value, 6)} for key, value in metrics.items()]
    )


def brier_score(y_true: pd.Series, y_prob: pd.Series) -> float:
    return float(((y_prob - y_true) ** 2).mean())


def log_loss_score(y_true: pd.Series, y_prob: pd.Series) -> float:
    clipped = y_prob.clip(1e-6, 1 - 1e-6)
    return float(
        -(
            y_true * clipped.map(math.log)
            + (1 - y_true) * (1 - clipped).map(math.log)
        ).mean()
    )


def roc_auc(y_true: pd.Series, y_prob: pd.Series) -> float:
    working = pd.DataFrame({"y_true": y_true, "y_prob": y_prob}).sort_values(
        "y_prob"
    )
    positives = float(working["y_true"].sum())
    negatives = float(len(working) - positives)
    if positives == 0 or negatives == 0:
        return 0.5

    ranks = working["y_prob"].rank(method="average")
    sum_ranks_positive = float(ranks[working["y_true"] == 1].sum())
    return (sum_ranks_positive - positives * (positives + 1) / 2.0) / (
        positives * negatives
    )


def calibration_table(candidate_pool: pd.DataFrame, n_bins: int = 10) -> pd.DataFrame:
    working = candidate_pool[["y_true", "pred_prob"]].copy()
    working["bin"] = pd.cut(
        working["pred_prob"],
        bins=pd.interval_range(start=0.0, end=1.0, periods=n_bins),
    )
    grouped = (
        working.groupby("bin", observed=True)
        .agg(
            count=("pred_prob", "size"),
            mean_pred_prob=("pred_prob", "mean"),
            observed_rate=("y_true", "mean"),
        )
        .reset_index()
    )
    grouped["bin_label"] = grouped["bin"].astype(str)
    grouped["gap"] = grouped["observed_rate"] - grouped["mean_pred_prob"]
    return grouped[["bin_label", "count", "mean_pred_prob", "observed_rate", "gap"]]


def difficulty_summary_table(candidate_pool: pd.DataFrame) -> pd.DataFrame:
    return (
        candidate_pool.groupby("difficulty_tier", observed=True)
        .agg(
            n=("case_id", "size"),
            default_rate=("y_true", "mean"),
            mean_pred_prob=("pred_prob", "mean"),
            mean_confidence=("confidence", "mean"),
            model_accuracy=("correct", "mean"),
            model_optimal_agreement=("model_optimal", "mean"),
        )
        .reset_index()
        .sort_values("difficulty_tier")
    )


def selection_cells_table(final_cases: pd.DataFrame) -> pd.DataFrame:
    return (
        final_cases.groupby(["difficulty_tier", "correct"], observed=True)
        .agg(
            n=("case_id", "size"),
            min_pred_prob=("pred_prob", "min"),
            mean_pred_prob=("pred_prob", "mean"),
            max_pred_prob=("pred_prob", "max"),
            mean_confidence=("confidence", "mean"),
        )
        .reset_index()
    )


def case_cost_table(final_cases: pd.DataFrame) -> pd.DataFrame:
    y_true = final_cases["y_true"].astype(int)
    strategy_definitions = {
        "always_approve": pd.Series([1] * len(final_cases)),
        "always_reject": pd.Series([0] * len(final_cases)),
        "model_at_0_5": (final_cases["pred_prob"] < 0.5).astype(int),
        "optimal_at_tau": (final_cases["pred_prob"] < TAU).astype(int),
    }
    rows = []
    for strategy_name, decisions in strategy_definitions.items():
        average_cost = sum(
            trial_cost(int(decision), int(label)) for decision, label in zip(decisions, y_true)
        ) / len(final_cases)
        rows.append(
            {
                "strategy": strategy_name,
                "avg_cost_per_case": round(float(average_cost), 6),
            }
        )
    return pd.DataFrame(rows)


def protocol_design_table(protocol_rotation: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in protocol_rotation.iterrows():
        for block_name in ["block_1", "block_2", "block_3"]:
            rows.append(
                {
                    "participant_group": row["participant_group"],
                    "block": block_name,
                    "protocol": row[f"{block_name}_protocol"],
                    "target_n": row.get("target_n"),
                }
            )
    return pd.DataFrame(rows)


def write_analysis_outputs(
    *,
    mode: str,
    final_cases: pd.DataFrame,
    practice_cases: pd.DataFrame,
    candidate_pool: pd.DataFrame,
    protocol_rotation: pd.DataFrame,
    manifest: dict[str, Any],
    warnings: list[str] | None = None,
    output_dir: Path | None = None,
    experiment_exports_dir: Path | None = None,
    exact_case_match: bool | None = None,
) -> Path:
    warnings = warnings or []
    output_path = ensure_directory(output_dir or ANALYSIS_DIR)
    tables_dir = ensure_directory(output_path / "tables")

    model_metrics = model_metrics_table(candidate_pool)
    calibration = calibration_table(candidate_pool)
    difficulty = difficulty_summary_table(candidate_pool)
    selection = selection_cells_table(final_cases)
    cost = case_cost_table(final_cases)
    protocol_design = protocol_design_table(protocol_rotation)

    final_cases.to_csv(tables_dir / "final_cases.csv", index=False)
    practice_cases.to_csv(tables_dir / "practice_cases.csv", index=False)
    candidate_pool.to_csv(tables_dir / "candidate_pool_scored.csv", index=False)
    protocol_rotation.to_csv(tables_dir / "protocol_rotation.csv", index=False)
    model_metrics.to_csv(tables_dir / "model_metrics.csv", index=False)
    calibration.to_csv(tables_dir / "calibration_bins.csv", index=False)
    difficulty.to_csv(tables_dir / "difficulty_summary.csv", index=False)
    selection.to_csv(tables_dir / "selection_cells.csv", index=False)
    cost.to_csv(tables_dir / "case_costs.csv", index=False)
    protocol_design.to_csv(tables_dir / "protocol_design.csv", index=False)

    export_bundle = None
    if experiment_exports_dir is not None:
        export_bundle = load_experiment_export_summary(experiment_exports_dir)
        if export_bundle:
            for table_name, table_df in export_bundle["tables"].items():
                table_df.to_csv(tables_dir / f"{table_name}.csv", index=False)
            warnings.extend(export_bundle["notes"])

    summary = {
        "mode": mode,
        "git_commit": git_commit_hash(),
        "official_frozen_dir": str(FROZEN_ARTIFACTS_DIR.relative_to(ROOT_DIR)),
        "analysis_dir": str(output_path.relative_to(ROOT_DIR)),
        "warnings": warnings,
        "exact_case_match_to_official_frozen": exact_case_match,
        "selection_manifest": manifest,
        "overview": {
            "final_cases": int(len(final_cases)),
            "practice_cases": int(len(practice_cases)),
            "candidate_pool_rows": int(len(candidate_pool)),
            "blocks": int(final_cases["block"].nunique()),
            "difficulty_tiers": sorted(
                final_cases["difficulty_tier"].dropna().astype(str).unique().tolist()
            ),
        },
        "model_metrics": {
            row["metric"]: row["value"] for row in model_metrics.to_dict(orient="records")
        },
        "participant_exports": export_bundle["summary"] if export_bundle else None,
    }
    write_json(output_path / "summary.json", summary)
    return output_path
