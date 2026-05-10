"""
Paper reproduction pipeline.

Loads participant exports from artifacts/db_exports/,
validates their schema, computes analysis-ready tables and figures,
and writes all outputs to artifacts/analysis/.

Usage:
    python3 -m codes.pipelines.reproduce_paper
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from codes.pipelines.common import (
    ANALYSIS_DIR,
    ARTIFACTS_DIR,
    FROZEN_ARTIFACTS_DIR,
    TAU,
    ensure_directory,
    load_frozen_tables,
    trial_cost,
    write_analysis_outputs,
)
from codes.pipelines.validate_artifacts import validate_frozen_artifacts

EXPORTS_DIR = ARTIFACTS_DIR / "db_exports"

REQUIRED_PARTICIPANT_COLS = {"id", "participant_group", "completed", "completed_at"}
REQUIRED_TRIAL_COLS = {
    "participant_id",
    "trial_index",
    "case_id",
    "block",
    "protocol",
    "difficulty_tier",
    "y_true",
    "pred_prob",
    "model_correct",
    "model_optimal",
    "decision_final",
    "prob_estimate_final",
    "total_trial_ms",
}
_SCORED_BLOCKS = {"block_1", "block_2", "block_3"}


def check_exports_exist(exports_dir: Path = EXPORTS_DIR) -> None:
    """Exit cleanly with clear message if required participant exports are missing."""
    missing = [
        name
        for name in ("participants.csv", "trials.csv")
        if not (exports_dir / name).exists()
    ]
    if missing:
        import sys
        print(
            "\n[ERROR] Final paper reproduction requires frozen Supabase exports.\n\n"
            f"Missing from {exports_dir}:\n"
            + "\n".join(f"  - {name}" for name in missing)
            + "\n\nExport participants and trials from Supabase and place them in "
            f"{exports_dir} before running paper mode."
        )
        sys.exit(1)


def validate_export_schema(
    participants: pd.DataFrame, trials: pd.DataFrame
) -> list[str]:
    """Return list of schema warnings (empty = OK). Does not raise."""
    warnings: list[str] = []

    missing_p = REQUIRED_PARTICIPANT_COLS - set(participants.columns)
    if missing_p:
        warnings.append(f"participants.csv missing columns: {sorted(missing_p)}")

    missing_t = REQUIRED_TRIAL_COLS - set(trials.columns)
    if missing_t:
        warnings.append(f"trials.csv missing columns: {sorted(missing_t)}")

    if "protocol" in trials.columns:
        hf = trials[trials["protocol"] == "human_first"]
        if not hf.empty:
            for col in ("decision_init", "prob_estimate_init"):
                if col not in trials.columns:
                    warnings.append(
                        f"human_first trials exist but '{col}' is absent from trials.csv"
                    )

    if "completed" in participants.columns:
        completed_ids = set(
            participants[participants["completed"].astype(bool)]["id"]
        )
        if "participant_id" in trials.columns and "block" in trials.columns:
            for pid in completed_ids:
                scored = trials[
                    (trials["participant_id"] == pid)
                    & (trials["block"].isin(_SCORED_BLOCKS))
                ]
                if len(scored) != 18:
                    warnings.append(
                        f"Participant {pid}: expected 18 scored trials, found {len(scored)}"
                    )

    return warnings


# ---------------------------------------------------------------------------
# Per-table builders
# ---------------------------------------------------------------------------

def _add_cost_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["trial_cost_val"] = df.apply(
        lambda r: trial_cost(int(r["decision_final"]), int(r["y_true"])), axis=1
    )
    df["optimal_cost_val"] = df.apply(
        lambda r: trial_cost(int(r["pred_prob"] < TAU), int(r["y_true"])), axis=1
    )
    df["cost_vs_optimal"] = df["trial_cost_val"] - df["optimal_cost_val"]
    df["decision_correct"] = (
        ((df["decision_final"] == 1) & (df["y_true"] == 0))
        | ((df["decision_final"] == 0) & (df["y_true"] == 1))
    ).astype(int)
    return df


def build_trials_clean(
    participants: pd.DataFrame, trials: pd.DataFrame
) -> pd.DataFrame:
    """Scored trials for completed participants only, with participant_group joined."""
    completed_ids = set(
        participants[participants["completed"].astype(bool)]["id"]
    )
    scored = trials[
        trials["participant_id"].isin(completed_ids)
        & trials["block"].isin(_SCORED_BLOCKS)
    ].copy()
    group_map = participants.set_index("id")["participant_group"]
    scored["participant_group"] = scored["participant_id"].map(group_map)
    return scored.reset_index(drop=True)


def build_participant_summary(
    participants: pd.DataFrame, trials: pd.DataFrame
) -> pd.DataFrame:
    """One row per completed participant with cost, accuracy, and relative performance."""
    scored = trials[trials["block"].isin(_SCORED_BLOCKS)].copy()
    scored = _add_cost_columns(scored)

    agg = (
        scored.groupby("participant_id")
        .agg(
            scored_trials=("trial_index", "count"),
            total_cost=("trial_cost_val", "sum"),
            optimal_cost=("optimal_cost_val", "sum"),
            cost_vs_optimal=("cost_vs_optimal", "sum"),
            accuracy=("decision_correct", "mean"),
        )
        .reset_index()
    )
    completed = participants[participants["completed"].astype(bool)][
        ["id", "participant_group"]
    ]
    result = completed.merge(
        agg, left_on="id", right_on="participant_id", how="left"
    ).drop(columns=["participant_id"], errors="ignore")
    return result.rename(columns={"id": "participant_id"})


def build_protocol_quality(trials: pd.DataFrame) -> pd.DataFrame:
    """Protocol-level decision quality and cost aggregation across all completed scored trials."""
    scored = trials[trials["block"].isin(_SCORED_BLOCKS)].copy()
    scored = _add_cost_columns(scored)
    return (
        scored.groupby("protocol")
        .agg(
            n_trials=("decision_final", "count"),
            n_participants=("participant_id", "nunique"),
            mean_accuracy=("decision_correct", "mean"),
            mean_cost=("trial_cost_val", "mean"),
            mean_optimal_cost=("optimal_cost_val", "mean"),
            mean_cost_vs_optimal=("cost_vs_optimal", "mean"),
        )
        .reset_index()
    )


def build_reliance_revision(trials: pd.DataFrame) -> pd.DataFrame | None:
    """Revision stats for human_first scored trials. Returns None if unavailable."""
    if "protocol" not in trials.columns:
        return None
    hf = trials[
        (trials["protocol"] == "human_first") & (trials["block"].isin(_SCORED_BLOCKS))
    ].copy()
    if hf.empty or "decision_init" not in hf.columns or "decision_final" not in hf.columns:
        return None

    hf["changed_decision"] = (hf["decision_init"] != hf["decision_final"]).astype(int)
    hf["revised_toward_reject"] = (
        (hf["decision_init"] == 1) & (hf["decision_final"] == 0)
    ).astype(int)
    hf["revised_toward_approve"] = (
        (hf["decision_init"] == 0) & (hf["decision_final"] == 1)
    ).astype(int)

    return pd.DataFrame(
        [
            {
                "protocol": "human_first",
                "n_trials": len(hf),
                "n_participants": int(hf["participant_id"].nunique()),
                "revision_rate": round(float(hf["changed_decision"].mean()), 4),
                "revised_toward_reject_rate": round(
                    float(hf["revised_toward_reject"].mean()), 4
                ),
                "revised_toward_approve_rate": round(
                    float(hf["revised_toward_approve"].mean()), 4
                ),
            }
        ]
    )


def build_calibration_analysis(trials: pd.DataFrame) -> pd.DataFrame:
    """Brier score and MAE of participant probability estimates per protocol."""
    mask = (
        trials["block"].isin(_SCORED_BLOCKS)
        & trials["prob_estimate_final"].notna()
    )
    scored = trials[mask].copy()
    if scored.empty:
        return pd.DataFrame()

    rows = []
    for protocol, group in scored.groupby("protocol"):
        y_true = group["y_true"].astype(float)
        prob = group["prob_estimate_final"].astype(float).clip(0.0, 1.0)
        brier = float(((prob - y_true) ** 2).mean())
        mae = float((prob - y_true).abs().mean())
        rows.append(
            {
                "protocol": protocol,
                "n_trials": len(group),
                "brier_score": round(brier, 4),
                "mean_absolute_error": round(mae, 4),
            }
        )
    return pd.DataFrame(rows)


def build_revision_paths(trials: pd.DataFrame) -> pd.DataFrame | None:
    """
    Revision path counts and cost impact for human_first scored trials.

    Returns a 4-row DataFrame (A→A, A→R, R→R, R→A) or None if unavailable.
    """
    if "protocol" not in trials.columns:
        return None
    hf = trials[
        (trials["protocol"] == "human_first") & (trials["block"].isin(_SCORED_BLOCKS))
    ].copy()
    if hf.empty or "decision_init" not in hf.columns or "decision_final" not in hf.columns:
        return None

    hf = _add_cost_columns(hf)
    hf["init_cost"] = hf.apply(
        lambda r: trial_cost(int(r["decision_init"]), int(r["y_true"])), axis=1
    )

    rows = []
    total = len(hf)
    for (init, final), group in hf.groupby(["decision_init", "decision_final"]):
        init_lbl = "A" if init == 1 else "R"
        final_lbl = "A" if final == 1 else "R"
        mean_cost_delta = float(group["trial_cost_val"].mean()) - float(group["init_cost"].mean())
        rows.append(
            {
                "path": f"{init_lbl}→{final_lbl}",
                "init_decision": int(init),
                "final_decision": int(final),
                "n": len(group),
                "rate": round(len(group) / total, 4),
                "mean_init_cost": round(float(group["init_cost"].mean()), 1),
                "mean_final_cost": round(float(group["trial_cost_val"].mean()), 1),
                "mean_cost_delta": round(mean_cost_delta, 1),
            }
        )
    return pd.DataFrame(rows) if rows else None


def build_case_level_summary(
    trials_clean: pd.DataFrame,
    final_cases: pd.DataFrame,
) -> pd.DataFrame:
    """
    Per-case participant response statistics joined with frozen design features.

    Requires trials_clean (scored completed trials). Returns empty DataFrame if
    trials_clean is empty.
    """
    from codes.pipelines.common import TAU

    if trials_clean.empty:
        return pd.DataFrame()

    tc = _add_cost_columns(trials_clean.copy())

    ai_protocols = {"ai_first", "human_first"}
    ai_mask = tc["protocol"].isin(ai_protocols) if "protocol" in tc.columns else pd.Series(False, index=tc.index)
    ai_trials = tc[ai_mask].copy()
    if not ai_trials.empty and "pred_prob" in ai_trials.columns:
        ai_trials["ai_recommendation"] = (ai_trials["pred_prob"] < TAU).astype(int)
        ai_trials["follows_ai"] = (
            ai_trials["decision_final"] == ai_trials["ai_recommendation"]
        ).astype(int)

    rows = []
    for case_id, group in tc.groupby("case_id"):
        row: dict = {
            "case_id": case_id,
            "n_observations": len(group),
            "approve_rate": round(float(group["decision_final"].mean()), 4),
            "accuracy_rate": round(float(group["decision_correct"].mean()), 4),
            "mean_cost": round(float(group["trial_cost_val"].mean()), 1),
        }
        if "prob_estimate_final" in group.columns:
            valid_prob = group["prob_estimate_final"].dropna()
            row["mean_prob_estimate"] = round(float(valid_prob.mean()), 4) if not valid_prob.empty else None
        ai_group = ai_trials[ai_trials["case_id"] == case_id] if not ai_trials.empty else pd.DataFrame()
        if not ai_group.empty and "follows_ai" in ai_group.columns:
            row["follow_ai_rate"] = round(float(ai_group["follows_ai"].mean()), 4)
            row["override_rate"] = round(1.0 - row["follow_ai_rate"], 4)
        else:
            row["follow_ai_rate"] = None
            row["override_rate"] = None
        rows.append(row)

    result = pd.DataFrame(rows)

    feature_cols = [
        c for c in [
            "case_id", "loan_amnt", "term", "int_rate", "dti", "revol_util",
            "home_ownership", "purpose", "credit_history_years", "log_annual_inc",
        ]
        if c in final_cases.columns
    ]
    result = result.merge(final_cases[feature_cols], on="case_id", how="left")
    return result


def build_hypothesis_skeleton() -> pd.DataFrame:
    """Placeholder hypothesis table with H1–H5 in 'pending' status.

    Replace the status/effect_size/ci_lower/ci_upper/p_value/interpretation
    columns with real statistical results after data collection.
    """
    return pd.DataFrame(
        [
            {
                "hypothesis": "H1",
                "label": "AI assistance reduces decision cost",
                "comparison": "no_ai vs ai_first",
                "metric": "mean_cost",
                "direction": "ai_first < no_ai",
                "status": "pending",
                "effect_size": None,
                "ci_lower": None,
                "ci_upper": None,
                "p_value": None,
                "interpretation": "Awaiting participant data.",
            },
            {
                "hypothesis": "H2",
                "label": "Human-first revision improves outcomes vs no AI",
                "comparison": "no_ai vs human_first",
                "metric": "mean_cost",
                "direction": "human_first < no_ai",
                "status": "pending",
                "effect_size": None,
                "ci_lower": None,
                "ci_upper": None,
                "p_value": None,
                "interpretation": "Awaiting participant data.",
            },
            {
                "hypothesis": "H3",
                "label": "Over-reliance: participants follow AI even when AI is incorrect",
                "comparison": "human_first trials, AI-incorrect cases",
                "metric": "follow_ai_rate when model_correct=0",
                "direction": "follow_rate > 0.5",
                "status": "pending",
                "effect_size": None,
                "ci_lower": None,
                "ci_upper": None,
                "p_value": None,
                "interpretation": "Awaiting participant data.",
            },
            {
                "hypothesis": "H4",
                "label": "AI access improves probability calibration",
                "comparison": "no_ai vs ai_first vs human_first",
                "metric": "brier_score",
                "direction": "ai_first < no_ai",
                "status": "pending",
                "effect_size": None,
                "ci_lower": None,
                "ci_upper": None,
                "p_value": None,
                "interpretation": "Awaiting participant data.",
            },
            {
                "hypothesis": "H5",
                "label": "AI correctness moderates reliance rate",
                "comparison": "correct vs incorrect AI cases in human_first",
                "metric": "follow_ai_rate",
                "direction": "follow_rate higher when AI correct",
                "status": "pending",
                "effect_size": None,
                "ci_lower": None,
                "ci_upper": None,
                "p_value": None,
                "interpretation": "Awaiting participant data.",
            },
        ]
    )


# ---------------------------------------------------------------------------
# Figure generation
# ---------------------------------------------------------------------------

def write_paper_figures(
    trials_clean: pd.DataFrame,
    protocol_quality: pd.DataFrame,
    reliance: pd.DataFrame | None,
    figures_dir: Path,
) -> None:
    """Generate static matplotlib figures for the paper. Skips gracefully if unavailable."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib not available — skipping figure generation.")
        return

    figures_dir.mkdir(parents=True, exist_ok=True)

    # Figure 1: Average cost by protocol
    if not protocol_quality.empty and "mean_cost" in protocol_quality.columns:
        fig, ax = plt.subplots(figsize=(7, 4))
        protocols = protocol_quality["protocol"].tolist()
        costs = protocol_quality["mean_cost"].tolist()
        colors = ["#4a90d9", "#d77a2f", "#1f7a8c"][: len(protocols)]
        ax.bar(protocols, costs, color=colors)
        if "mean_optimal_cost" in protocol_quality.columns:
            optimal = float(protocol_quality["mean_optimal_cost"].mean())
            ax.axhline(optimal, color="#b5473a", linestyle="--", label=f"Optimal (τ={TAU:.3f})")
            ax.legend()
        ax.set_xlabel("Protocol")
        ax.set_ylabel("Mean cost per trial ($)")
        ax.set_title("Decision Cost by Protocol")
        fig.tight_layout()
        fig.savefig(figures_dir / "avg_cost_by_protocol.png", dpi=150, bbox_inches="tight")
        plt.close(fig)

    # Figure 2: Participant probability calibration by protocol
    if not trials_clean.empty and "prob_estimate_final" in trials_clean.columns:
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Perfect")
        palette = ["#4a90d9", "#d77a2f", "#1f7a8c"]
        for i, (protocol, group) in enumerate(trials_clean.groupby("protocol")):
            prob = group["prob_estimate_final"].astype(float).clip(0.0, 1.0)
            y_true = group["y_true"].astype(float)
            bin_edges = np.linspace(0, 1, 11)
            bin_idx = np.clip(np.digitize(prob, bin_edges) - 1, 0, 9)
            bin_mean_prob, bin_mean_true = [], []
            for b in range(10):
                mask = bin_idx == b
                if mask.sum() > 0:
                    bin_mean_prob.append(float(prob[mask].mean()))
                    bin_mean_true.append(float(y_true[mask].mean()))
            if bin_mean_prob:
                color = palette[i % len(palette)]
                ax.plot(bin_mean_prob, bin_mean_true, "o-", color=color, label=protocol, alpha=0.85)
        ax.set_xlabel("Mean probability estimate")
        ax.set_ylabel("Observed default rate")
        ax.set_title("Participant Probability Calibration by Protocol")
        ax.legend()
        fig.tight_layout()
        fig.savefig(figures_dir / "calibration_by_protocol.png", dpi=150, bbox_inches="tight")
        plt.close(fig)

    # Figure 3: Revision rate (human_first only)
    if reliance is not None and not reliance.empty:
        fig, ax = plt.subplots(figsize=(5, 4))
        rate = float(reliance["revision_rate"].iloc[0])
        toward_reject = float(reliance.get("revised_toward_reject_rate", pd.Series([0])).iloc[0])
        toward_approve = float(reliance.get("revised_toward_approve_rate", pd.Series([0])).iloc[0])
        ax.bar(
            ["Any revision", "→ Reject", "→ Approve"],
            [rate, toward_reject, toward_approve],
            color=["#4a90d9", "#b5473a", "#1f7a8c"],
        )
        ax.set_ylim(0, 1)
        ax.set_ylabel("Rate")
        ax.set_title("Decision Revision Rates (human_first)")
        fig.tight_layout()
        fig.savefig(figures_dir / "revision_rate.png", dpi=150, bbox_inches="tight")
        plt.close(fig)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_paper_reproduction(
    output_dir: Path | None = None,
    exports_dir: Path | None = None,
) -> Path:
    """
    Reproduce final paper results from frozen participant exports.

    Fails clearly if exports are missing.
    Returns the output directory path.
    """
    exp_dir = exports_dir or EXPORTS_DIR
    out_dir = output_dir or ANALYSIS_DIR

    check_exports_exist(exp_dir)

    participants = pd.read_csv(exp_dir / "participants.csv")
    trials = pd.read_csv(exp_dir / "trials.csv")

    schema_warnings = validate_export_schema(participants, trials)
    for w in schema_warnings:
        print(f"  WARNING: {w}")

    quiz_path = exp_dir / "quiz_responses.csv"
    if quiz_path.exists():
        print(f"  quiz_responses.csv found ({len(pd.read_csv(quiz_path))} rows)")

    # Validate and load frozen design artifacts
    validate_frozen_artifacts(FROZEN_ARTIFACTS_DIR)
    tables = load_frozen_tables(FROZEN_ARTIFACTS_DIR)

    # Core analysis output (design tables + basic participant protocol/reliance tables
    # generated by write_analysis_outputs via load_experiment_export_summary)
    out_path = write_analysis_outputs(
        mode="paper",
        final_cases=tables["final_cases"],
        practice_cases=tables["practice_cases"],
        candidate_pool=tables["candidate_pool"],
        protocol_rotation=tables["protocol_rotation"],
        manifest=tables["manifest"],
        warnings=schema_warnings,
        output_dir=out_dir,
        experiment_exports_dir=exp_dir,
        exact_case_match=True,
    )

    # Additional paper-specific tables
    tables_dir = ensure_directory(out_path / "tables")
    figures_dir = ensure_directory(out_path / "figures")

    trials_clean = build_trials_clean(participants, trials)
    trials_clean.to_csv(tables_dir / "trials_clean.csv", index=False)

    participants_clean = build_participant_summary(participants, trials)
    participants_clean.to_csv(tables_dir / "participants_clean.csv", index=False)

    protocol_outcomes = build_protocol_quality(trials)
    protocol_outcomes.to_csv(tables_dir / "protocol_outcomes.csv", index=False)

    reliance_summary = build_reliance_revision(trials)
    if reliance_summary is not None:
        reliance_summary.to_csv(tables_dir / "reliance_summary.csv", index=False)

    calibration_by_protocol = build_calibration_analysis(trials)
    if not calibration_by_protocol.empty:
        calibration_by_protocol.to_csv(tables_dir / "calibration_by_protocol.csv", index=False)

    revision_paths = build_revision_paths(trials)
    if revision_paths is not None:
        revision_paths.to_csv(tables_dir / "revision_paths.csv", index=False)

    case_level_summary = build_case_level_summary(trials_clean, tables["final_cases"])
    if not case_level_summary.empty:
        case_level_summary.to_csv(tables_dir / "case_level_summary.csv", index=False)

    build_hypothesis_skeleton().to_csv(tables_dir / "hypothesis_summary.csv", index=False)

    write_paper_figures(trials_clean, protocol_outcomes, reliance_summary, figures_dir)

    n_completed = int(participants["completed"].astype(bool).sum()) if "completed" in participants.columns else len(participants)
    print(f"  participants (completed): {n_completed}")
    print(f"  scored trials (completed participants): {len(trials_clean)}")

    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproduce final paper results from frozen participant exports."
    )
    parser.add_argument(
        "--output-dir",
        default=str(ANALYSIS_DIR),
        help="Directory where analysis outputs are written.",
    )
    parser.add_argument(
        "--exports-dir",
        default=str(EXPORTS_DIR),
        help="Directory containing frozen participant exports.",
    )
    args = parser.parse_args()

    out = run_paper_reproduction(
        output_dir=Path(args.output_dir),
        exports_dir=Path(args.exports_dir),
    )
    print(f"Paper reproduction outputs written to {out}")


if __name__ == "__main__":
    main()
