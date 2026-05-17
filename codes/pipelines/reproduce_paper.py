"""
Final paper reproduction pipeline.

This module is the non-notebook version of codes/notebooks/analysis.ipynb.
It intentionally keeps the same core calculations, table set, color palette,
and figure logic as the notebook, while updating paths to the final repo layout:

Inputs:
    data/experiment_exports/{participants.csv,trials.csv,quiz_responses.csv}
    artifacts/frozen/*

Outputs:
    artifacts/tables/
        protocol_outcomes.csv
        protocol_contrasts.csv
        human_first_correction_matrix.csv
        woa_summary.csv
        case_level_cost.csv
    artifacts/figures/
        cost_accuracy_by_protocol.png
        human_first_correction_matrix.png
        woa_distribution.png
        case_risk_cost_scatter.png
        normative_deviation_by_difficulty.png
    artifacts/summary.json

The default reproduction path does not require data/raw/loan.csv.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import binomtest

from codes.pipelines.validate_artifacts import validate_frozen_artifacts

warnings.filterwarnings("ignore", category=RuntimeWarning, module="statsmodels")
warnings.filterwarnings("ignore", message=".*covariance.*", module="statsmodels")
warnings.filterwarnings("ignore", message=".*Hessian.*", module="statsmodels")
warnings.filterwarnings("ignore", message=".*singular.*", module="statsmodels")


# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current] + list(current.parents):
        if (candidate / "artifacts").exists() and (candidate / "codes").exists():
            return candidate
    raise RuntimeError("Could not locate repository root. Run from inside the capstone repo.")


ROOT = find_repo_root()
EXPORTS_DIR = ROOT / "data" / "experiment_exports"
FROZEN_DIR = ROOT / "artifacts" / "frozen"
ARTIFACTS_DIR = ROOT / "artifacts"
TABLES_DIR = ARTIFACTS_DIR / "tables"
FIGURES_DIR = ARTIFACTS_DIR / "figures"

TAU = 1 / 6
C_FN = 5
C_FP = 1

PROTOCOLS = ["no_ai", "ai_first", "human_first"]
TIERS = ["easy", "medium", "hard"]

PROTOCOL_LABELS = {
    "no_ai": "No AI",
    "ai_first": "AI-first",
    "human_first": "Human-first",
}

# Same notebook-facing figure style as analysis.ipynb.
COST_COLOR = "#34445C"
ACCURACY_COLOR = "#0F7F73"
TEXT_COLOR = "#111827"
MUTED_TEXT = "#6B7280"
LIGHT_GRID = "#E5E7EB"
CELL_GRAY = "#DFE3E8"
CELL_GREEN = "#C8F3E8"
CELL_RED = "#F6D6D6"
AXIS_COLOR = "#CBD5E1"
WOA_NO_MOVE_COLOR = "#98A2B3"
WOA_MEDIAN_COLOR = "#C96F32"
TIER_COLORS = {
    "easy": "#5DAE8B",
    "medium": "#E68A4F",
    "hard": "#D96A6A",
}

EXPECTED_TABLES = [
    "protocol_outcomes.csv",
    "protocol_contrasts.csv",
    "human_first_correction_matrix.csv",
    "woa_summary.csv",
    "case_level_cost.csv",
]

EXPECTED_FIGURES = [
    "cost_accuracy_by_protocol.png",
    "human_first_correction_matrix.png",
    "woa_distribution.png",
    "case_risk_cost_scatter.png",
    "normative_deviation_by_difficulty.png",
]

# Stale outputs created by earlier over-expanded pipeline versions. Removed so the
# final artifact directories stay compact and aligned with analysis.ipynb.
STALE_TABLES = [
    "trials_clean.csv",
    "participants_clean.csv",
    "participant_protocol_cost.csv",
    "participant_protocol_accuracy.csv",
    "cost_contrasts.csv",
    "accuracy_contrasts.csv",
    "calibration_by_protocol.csv",
    "human_first_revision_paths.csv",
    "woa_trials.csv",
    "normative_deviation.csv",
    "case_level_summary.csv",
    "model_metrics.csv",
    "calibration_bins.csv",
    "difficulty_summary.csv",
    "selection_cells.csv",
    "case_costs.csv",
    "protocol_design.csv",
]


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_previous_outputs(tables_dir: Path, figures_dir: Path) -> None:
    """Remove stale pipeline outputs so artifacts remain compact and intentional."""
    ensure_dir(tables_dir)
    ensure_dir(figures_dir)

    for name in EXPECTED_TABLES + STALE_TABLES:
        p = tables_dir / name
        if p.exists():
            p.unlink()

    for name in EXPECTED_FIGURES:
        p = figures_dir / name
        if p.exists():
            p.unlink()
        pdf = figures_dir / name.replace(".png", ".pdf")
        if pdf.exists():
            pdf.unlink()


def trial_cost(decision: int, y_true: int) -> int:
    """Asymmetric trial cost. decision: 1=approve, 0=reject. y_true: 1=default, 0=paid."""
    if decision == 1 and y_true == 1:
        return C_FN
    if decision == 0 and y_true == 0:
        return C_FP
    return 0


def fmt_p(p: float | None) -> str:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return "p = n/a"
    if p < 0.0001:
        return "p < 0.0001"
    if p < 0.001:
        return "p < 0.001"
    return f"p = {p:.3f}"


def paired_ttest(df: pd.DataFrame, a: str, b: str) -> dict[str, Any]:
    """Paired t-test on per-participant protocol means."""
    if a not in df.columns or b not in df.columns:
        return {"msg": f"columns missing: {a}, {b}"}

    diff = (df[a] - df[b]).dropna()
    n = len(diff)
    if n < 3:
        return {"msg": f"n={n} too small"}

    t_stat, p_val = stats.ttest_1samp(diff, 0)
    mean_diff = float(diff.mean())
    se = float(diff.sem())
    crit = stats.t.ppf(0.975, df=n - 1)
    ci = (mean_diff - crit * se, mean_diff + crit * se)
    sd = float(diff.std(ddof=1))
    cohen_d = mean_diff / sd if sd > 0 else 0.0

    return {
        "n": n,
        "mean_diff": round(mean_diff, 4),
        "ci95": (round(ci[0], 4), round(ci[1], 4)),
        "t": round(float(t_stat), 3),
        "p": float(p_val),
        "d": round(cohen_d, 3),
    }


def ttest_row(pp_df: pd.DataFrame, a: str, b: str) -> dict[str, Any]:
    row = paired_ttest(pp_df, a, b)
    row["label_a"] = PROTOCOL_LABELS[a]
    row["label_b"] = PROTOCOL_LABELS[b]
    if "msg" not in row:
        row["mean_a"] = round(float(pp_df[a].mean()), 4)
        row["mean_b"] = round(float(pp_df[b].mean()), 4)
    return row


def run_contrasts(pp_df: pd.DataFrame) -> list[dict[str, Any]]:
    planned = [
        ("no_ai", "ai_first"),
        ("no_ai", "human_first"),
        ("ai_first", "human_first"),
    ]
    return [ttest_row(pp_df, a, b) for a, b in planned]


def contrast_dataframe(rows: list[dict[str, Any]], metric: str) -> pd.DataFrame:
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        if "msg" in row:
            out_rows.append(
                {
                    "metric": metric,
                    "comparison": f"{row['label_a']} vs {row['label_b']}",
                    "note": row["msg"],
                }
            )
            continue
        out_rows.append(
            {
                "metric": metric,
                "comparison": f"{row['label_a']} vs {row['label_b']}",
                "mean_a": row["mean_a"],
                "mean_b": row["mean_b"],
                "delta_mean_a_minus_b": row["mean_diff"],
                "ci95_low": row["ci95"][0],
                "ci95_high": row["ci95"][1],
                "t": row["t"],
                "p": row["p"],
                "d": row["d"],
                "n": row["n"],
            }
        )
    return pd.DataFrame(out_rows)


def print_contrast_table(rows: list[dict[str, Any]]) -> None:
    header = f"{'Comparison':<28} {'Mean A':>7} {'Mean B':>7} {'Δ':>8} {'95% CI':>20} {'t':>7} {'p':>12} {'d':>7}"
    print(header)
    print("-" * len(header))
    for row in rows:
        if "msg" in row:
            print(f" {row['label_a']} vs {row['label_b']}: {row['msg']}")
            continue
        ci_s = f"({row['ci95'][0]:+.3f}, {row['ci95'][1]:+.3f})"
        print(
            f"{row['label_a'] + ' vs ' + row['label_b']:<28}"
            f"{row['mean_a']:>7.4f} {row['mean_b']:>7.4f} {row['mean_diff']:>+8.4f}"
            f"{ci_s:>20} {row['t']:>7.3f} {fmt_p(row['p']):>12} {row['d']:>7.3f}"
        )


def save_fig(fig: Any, filename: str, figures_dir: Path = FIGURES_DIR, *, pad_inches: float = 0.02) -> None:
    """Save PNG only, matching analysis.ipynb and avoiding duplicated PDF artifacts."""
    out = figures_dir / filename
    fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=pad_inches)
    print(f"Saved figure: {out.relative_to(ROOT)}")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Loading and sample construction
# ---------------------------------------------------------------------------

def check_required_inputs(exports_dir: Path = EXPORTS_DIR) -> None:
    missing = [name for name in ["participants.csv", "trials.csv"] if not (exports_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            "Default reproduction requires Supabase exports in data/experiment_exports/.\n"
            f"Missing: {', '.join(missing)}\n"
            "Expected files:\n"
            "  data/experiment_exports/participants.csv\n"
            "  data/experiment_exports/trials.csv\n"
            "  data/experiment_exports/quiz_responses.csv  # optional for quiz appendix checks\n"
        )


def load_exports(exports_dir: Path = EXPORTS_DIR) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    check_required_inputs(exports_dir)
    participants_raw = pd.read_csv(exports_dir / "participants.csv")
    trials_raw = pd.read_csv(exports_dir / "trials.csv")

    quiz_path = exports_dir / "quiz_responses.csv"
    quiz_raw = pd.read_csv(quiz_path) if quiz_path.exists() else pd.DataFrame()

    prob_max = trials_raw["prob_estimate_final"].dropna().max()
    prob_scale = 100.0 if prob_max > 1.0 else 1.0
    if prob_scale == 100.0:
        for col in ("prob_estimate_final", "prob_estimate_init"):
            if col in trials_raw.columns:
                trials_raw[col] = trials_raw[col] / 100.0

    print(f"prob scale     : {'0–100 (divided)' if prob_scale == 100 else '0–1 (native)'}")
    print(f"participants   : {len(participants_raw)}")
    print(f"trials         : {len(trials_raw)}")
    print(f"quiz rows      : {len(quiz_raw)}")
    return participants_raw, trials_raw, quiz_raw


def build_analysis_sample(participants_raw: pd.DataFrame, trials_raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, set[Any]]:
    comp_mask = participants_raw["completed"].fillna(False).astype(bool)
    n_total = len(participants_raw)
    n_completed = int(comp_mask.sum())
    n_dropped = n_total - n_completed

    print("\n[Sample]")
    print(f"Enrolled       : {n_total}")
    print(f"Completed      : {n_completed} ({n_completed / n_total:.1%})")
    print(f"Dropped        : {n_dropped} ({n_dropped / n_total:.1%})")

    group_counts = participants_raw.loc[comp_mask, "participant_group"].value_counts().sort_index()
    print("\nGroup balance among completed participants:")
    print(group_counts.to_string())
    if n_completed >= 3:
        chi2, p_chi = stats.chisquare(group_counts.values)
        print(f"chi2={chi2:.3f} {fmt_p(float(p_chi))}")

    completed_ids = set(participants_raw.loc[comp_mask, "id"])
    scored_a = trials_raw[
        trials_raw["participant_id"].isin(completed_ids)
        & (trials_raw["trial_index"] >= 1)
    ].copy()
    participants_a = participants_raw[participants_raw["id"].isin(completed_ids)].copy()

    tpp = scored_a.groupby("participant_id").size()
    print(f"\nScored trials  : {len(scored_a)} (expected {len(completed_ids) * 18})")
    print(f"Trials/person  : min={tpp.min()} max={tpp.max()} mean={tpp.mean():.1f}")

    if n_completed != 100:
        raise AssertionError(f"Expected 100 completed participants, got {n_completed}")
    if len(scored_a) != 1800:
        raise AssertionError(f"Expected 1800 scored trials, got {len(scored_a)}")
    if not (tpp.min() == 18 and tpp.max() == 18):
        raise AssertionError("Each completed participant should have 18 scored trials")

    return participants_a, scored_a, completed_ids


def add_derived_variables(scored_a: pd.DataFrame) -> pd.DataFrame:
    scored_a = scored_a.copy()
    scored_a["correct"] = (
        ((scored_a["decision_final"] == 1) & (scored_a["y_true"] == 0))
        | ((scored_a["decision_final"] == 0) & (scored_a["y_true"] == 1))
    ).astype(int)

    scored_a["trial_cost"] = scored_a.apply(
        lambda r: trial_cost(int(r["decision_final"]), int(r["y_true"])),
        axis=1,
    )
    scored_a["opt_cost"] = scored_a.apply(
        lambda r: trial_cost(1 if r["pred_prob"] < TAU else 0, int(r["y_true"])),
        axis=1,
    )
    scored_a["cost_excess"] = scored_a["trial_cost"] - scored_a["opt_cost"]
    scored_a["difficulty_tier"] = scored_a["difficulty_tier"].astype(
        pd.CategoricalDtype(TIERS, ordered=True)
    )
    scored_a["impl_tau"] = (scored_a["prob_estimate_final"] < TAU).astype(int)
    scored_a["impl_half"] = (scored_a["prob_estimate_final"] < 0.5).astype(int)

    cons_tau = (scored_a["decision_final"] == scored_a["impl_tau"]).mean()
    cons_half = (scored_a["decision_final"] == scored_a["impl_half"]).mean()

    print("\n[Derived variables]")
    print("Derived        : correct, trial_cost, opt_cost, cost_excess")
    print(
        f"prob range     : [{scored_a['prob_estimate_final'].min():.3f}, "
        f"{scored_a['prob_estimate_final'].max():.3f}]"
    )
    print(f"Decision consistency: tau=0.167 -> {cons_tau:.1%} | tau=0.5 -> {cons_half:.1%}")
    return scored_a


# ---------------------------------------------------------------------------
# Analysis sections
# ---------------------------------------------------------------------------

def analyze_primary_cost(scored_a: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    pp_cost = (
        scored_a.groupby(["participant_id", "protocol"])["trial_cost"]
        .mean()
        .unstack("protocol")
    )
    cost_by_proto = (
        scored_a.groupby("protocol")[["trial_cost", "opt_cost"]]
        .mean()
        .round(4)
        .reindex(PROTOCOLS)
    )

    print("\n[Primary outcome: decision cost]")
    print("Protocol means:")
    print(cost_by_proto.to_string())
    print(f"AI benchmark (opt_cost overall): {scored_a['opt_cost'].mean():.4f}")

    rows = run_contrasts(pp_cost)
    print(f"\nPaired t-tests — trial cost (N={len(pp_cost)})")
    print_contrast_table(rows)
    return pp_cost, cost_by_proto, rows


def analyze_accuracy(scored_a: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    pp_acc = (
        scored_a.groupby(["participant_id", "protocol"])["correct"]
        .mean()
        .unstack("protocol")
    )
    rows = run_contrasts(pp_acc)
    print(f"\n[Secondary outcome: accuracy]\nPaired t-tests — accuracy (N={len(pp_acc)})")
    print_contrast_table(rows)
    return pp_acc, rows


def analyze_human_first(scored_a: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, dict[str, Any]]:
    hf_switch = scored_a[scored_a["protocol"] == "human_first"].dropna(
        subset=["decision_init", "decision_final", "y_true"]
    ).copy()

    hf_switch["correct_init"] = (
        ((hf_switch["decision_init"] == 1) & (hf_switch["y_true"] == 0))
        | ((hf_switch["decision_init"] == 0) & (hf_switch["y_true"] == 1))
    ).astype(int)
    hf_switch["correct_final"] = (
        ((hf_switch["decision_final"] == 1) & (hf_switch["y_true"] == 0))
        | ((hf_switch["decision_final"] == 0) & (hf_switch["y_true"] == 1))
    ).astype(int)

    g_stay_ok = int(((hf_switch["correct_init"] == 1) & (hf_switch["correct_final"] == 1)).sum())
    g_improved = int(((hf_switch["correct_init"] == 0) & (hf_switch["correct_final"] == 1)).sum())
    g_stay_bad = int(((hf_switch["correct_init"] == 0) & (hf_switch["correct_final"] == 0)).sum())
    g_worsened = int(((hf_switch["correct_init"] == 1) & (hf_switch["correct_final"] == 0)).sum())
    g_n = len(hf_switch)

    print("\n[Human-first correction analysis]")
    print(f"N human-first trials: {g_n}")
    print(f"  Stayed correct : {g_stay_ok:5d} ({100 * g_stay_ok / g_n:.1f}%)")
    print(f"  Improved       : {g_improved:5d} ({100 * g_improved / g_n:.1f}%)")
    print(f"  Stayed wrong   : {g_stay_bad:5d} ({100 * g_stay_bad / g_n:.1f}%)")
    print(f"  Worsened       : {g_worsened:5d} ({100 * g_worsened / g_n:.1f}%)")
    print(f"  Net gain       : {g_improved - g_worsened:+d} ({100 * (g_improved - g_worsened) / g_n:.1f} pp)")

    n_changed = g_improved + g_worsened
    binom_p = np.nan
    if n_changed > 0:
        binom_res = binomtest(g_improved, n_changed, 0.5, alternative="greater")
        binom_p = float(binom_res.pvalue)
        print(f"Sign test among changers: {g_improved} improved vs {g_worsened} worsened; {fmt_p(binom_p)}")

    correction_table = pd.DataFrame(
        {
            "Final correct": [g_stay_ok, g_improved],
            "Final wrong": [g_worsened, g_stay_bad],
        },
        index=["Initial correct", "Initial wrong"],
    )

    # WOA
    hf = scored_a[
        (scored_a["protocol"] == "human_first")
        & scored_a["prob_estimate_init"].notna()
        & scored_a["decision_init"].notna()
    ].copy()
    n_hf = len(hf)

    if n_hf == 0:
        n_woa_valid = n_no_adj_woa = n_adj_woa = n_denom_excl = 0
        hf_woa = pd.DataFrame()
        w_all = w_adj = pd.Series(dtype=float)
    else:
        hf["prob_moved"] = (hf["prob_estimate_final"] - hf["prob_estimate_init"]).abs()
        hf["denom"] = hf["pred_prob"] - hf["prob_estimate_init"]
        hf_woa = hf[hf["denom"].abs() >= 0.01].copy()
        n_woa_valid = len(hf_woa)
        n_denom_excl = n_hf - n_woa_valid
        hf_woa["woa"] = (
            (hf_woa["prob_estimate_final"] - hf_woa["prob_estimate_init"])
            / hf_woa["denom"]
        ).clip(-1, 2)
        no_adj_mask_woa = hf_woa["prob_moved"] < 0.01
        n_no_adj_woa = int(no_adj_mask_woa.sum())
        n_adj_woa = n_woa_valid - n_no_adj_woa
        w_all = hf_woa["woa"].dropna()
        w_adj = hf_woa.loc[~no_adj_mask_woa, "woa"].dropna()

    print("\n[Weight of Advice]")
    print(f"Total human-first trials       : {n_hf}")
    print(f"Denom-excluded (AI ≈ init_prob): {n_denom_excl}")
    print(f"WOA-valid                      : {n_woa_valid}")
    if n_woa_valid:
        print(f"No movement                    : {n_no_adj_woa} ({n_no_adj_woa / n_woa_valid:.1%})")
        print(f"Adjusted trials                : {n_adj_woa} ({n_adj_woa / n_woa_valid:.1%})")
        print(f"Median WOA among adjusted      : {w_adj.median():.3f}")

    woa_summary = pd.DataFrame(
        [
            {
                "human_first_trials": n_hf,
                "denom_excluded": n_denom_excl,
                "woa_valid": n_woa_valid,
                "no_adjustment": n_no_adj_woa,
                "adjusted_trials": n_adj_woa,
                "all_mean": float(w_all.mean()) if len(w_all) else np.nan,
                "all_median": float(w_all.median()) if len(w_all) else np.nan,
                "adjusted_mean": float(w_adj.mean()) if len(w_adj) else np.nan,
                "adjusted_median": float(w_adj.median()) if len(w_adj) else np.nan,
            }
        ]
    )

    hf_counts = {
        "g_stay_ok": g_stay_ok,
        "g_worsened": g_worsened,
        "g_improved": g_improved,
        "g_stay_bad": g_stay_bad,
        "g_n": g_n,
        "binom_p": binom_p,
        "n_hf": n_hf,
        "n_woa_valid": n_woa_valid,
        "n_no_adj_woa": n_no_adj_woa,
        "n_adj_woa": n_adj_woa,
        "n_denom_excl": n_denom_excl,
    }
    return correction_table, woa_summary, w_all, w_adj, hf_counts


def analyze_case_level(scored_a: pd.DataFrame) -> tuple[pd.DataFrame, float, float]:
    case_stats = (
        scored_a.groupby("case_id", observed=True)
        .agg(
            difficulty_tier=("difficulty_tier", "first"),
            pred_prob=("pred_prob", "first"),
            y_true=("y_true", "first"),
            mean_cost=("trial_cost", "mean"),
            mean_accuracy=("correct", "mean"),
            n_trials=("trial_cost", "size"),
        )
        .reset_index()
        .sort_values("pred_prob")
        .round({"mean_cost": 4, "mean_accuracy": 4, "pred_prob": 4})
    )

    if len(case_stats) != 18:
        raise AssertionError(f"Expected 18 cases, got {len(case_stats)}")
    if not case_stats["n_trials"].eq(100).all():
        raise AssertionError(f"n_trials != 100 for:\n{case_stats[case_stats['n_trials'] != 100]}")

    print("\n[Case-level analysis]")
    print("Case-level cost and accuracy, sorted by AI predicted default probability:")
    print(case_stats.to_string(index=False))
    print("\nMean by difficulty tier:")
    print(
        case_stats.groupby("difficulty_tier", observed=True)[["mean_cost", "mean_accuracy", "pred_prob"]]
        .mean()
        .round(4)
        .reindex(TIERS)
        .to_string()
    )

    rho_case, p_rho_case = stats.spearmanr(case_stats["pred_prob"], case_stats["mean_cost"])
    print(f"\nSpearman: pred_prob vs mean_cost rho={rho_case:.3f} {fmt_p(float(p_rho_case))}")
    return case_stats, float(rho_case), float(p_rho_case)


def analyze_normative_deviation(scored_a: pd.DataFrame) -> pd.DataFrame:
    scored_a["optimal_dec"] = (scored_a["pred_prob"] < TAU).astype(int)
    scored_a["deviates"] = (scored_a["decision_final"] != scored_a["optimal_dec"]).astype(int)
    dev_by_tier = (
        scored_a.groupby("difficulty_tier", observed=True)
        .agg(deviation_rate=("deviates", "mean"), n=("deviates", "count"))
        .round(4)
        .reindex(TIERS)
    )

    print("\n[Normative deviation by difficulty]")
    print(dev_by_tier.to_string())
    return dev_by_tier.reset_index()


# ---------------------------------------------------------------------------
# Figures: copied intentionally from analysis.ipynb, with only path/display changes
# ---------------------------------------------------------------------------

def setup_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "figure.dpi": 300,
        }
    )
    return plt


def make_figures(
    pp_cost: pd.DataFrame,
    pp_acc: pd.DataFrame,
    correction_table: pd.DataFrame,
    w_all: pd.Series,
    w_adj: pd.Series,
    hf_counts: dict[str, Any],
    case_stats: pd.DataFrame,
    dev_by_tier: pd.DataFrame,
    figures_dir: Path = FIGURES_DIR,
) -> list[str]:
    plt = setup_matplotlib()
    generated: list[str] = []

    # Figure 1 — cost and accuracy by protocol
    protocol_order = ["no_ai", "ai_first", "human_first"]
    labels = [PROTOCOL_LABELS[p] for p in protocol_order]
    cost_means_plot = [pp_cost[p].mean() for p in protocol_order]
    acc_means_plot = [pp_acc[p].mean() for p in protocol_order]
    ypos = np.arange(len(protocol_order))

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7))
    fig.patch.set_facecolor("white")

    panels = [
        {
            "ax": axes[0],
            "values": cost_means_plot,
            "color": COST_COLOR,
            "title": "(a) Mean trial cost",
            "fmt": "{:.3f}",
            "xlim": (0.0, max(cost_means_plot) * 1.22),
        },
        {
            "ax": axes[1],
            "values": acc_means_plot,
            "color": ACCURACY_COLOR,
            "title": "(b) Accuracy",
            "fmt": "{:.1%}",
            "xlim": (0.0, min(1.0, max(acc_means_plot) * 1.22)),
        },
    ]

    for panel in panels:
        ax = panel["ax"]
        values = panel["values"]
        xmin, xmax = panel["xlim"]
        bars = ax.barh(ypos, values, color=panel["color"], height=0.54, edgecolor="none")
        ax.set_yticks(ypos)
        ax.set_yticklabels(labels, fontsize=9, color=TEXT_COLOR)
        ax.invert_yaxis()
        ax.set_xlim(xmin, xmax)
        ax.set_title(panel["title"], loc="left", fontsize=10, fontweight="bold", pad=5, color=TEXT_COLOR)
        label_offset = (xmax - xmin) * 0.015
        for bar, value in zip(bars, values):
            ax.text(
                value + label_offset,
                bar.get_y() + bar.get_height() / 2,
                panel["fmt"].format(value),
                ha="left",
                va="center",
                fontsize=8.5,
                color=TEXT_COLOR,
            )
        ax.grid(False)
        ax.tick_params(axis="x", bottom=False, labelbottom=False)
        ax.tick_params(axis="y", length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

    fig.suptitle(
        "Protocol-level outcomes",
        x=0.01,
        y=1.03,
        ha="left",
        fontsize=11,
        fontweight="bold",
        color=TEXT_COLOR,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94], w_pad=2.0)
    save_fig(fig, "cost_accuracy_by_protocol.png", figures_dir, pad_inches=0.02)
    plt.close(fig)
    generated.append("cost_accuracy_by_protocol.png")

    # Figure 2 — human-first correction matrix
    g_stay_ok = int(correction_table.loc["Initial correct", "Final correct"])
    g_worsened = int(correction_table.loc["Initial correct", "Final wrong"])
    g_improved = int(correction_table.loc["Initial wrong", "Final correct"])
    g_stay_bad = int(correction_table.loc["Initial wrong", "Final wrong"])

    matrix = np.array([[g_stay_ok, g_worsened], [g_improved, g_stay_bad]], dtype=float)
    cell_bg = np.array([[CELL_GRAY, CELL_RED], [CELL_GREEN, CELL_GRAY]])
    cell_fg = np.array([[TEXT_COLOR, "#B91C1C"], ["#0F766E", TEXT_COLOR]])
    cell_labels = np.array([["Stayed correct", "Worsened"], ["Improved", "Stayed wrong"]])

    fig, ax = plt.subplots(figsize=(3.35, 2.45))
    fig.patch.set_facecolor("white")
    ax.set_xlim(0, 2)
    ax.set_ylim(0, 2)
    ax.set_aspect("equal")
    for i in range(2):
        for j in range(2):
            ax.add_patch(
                plt.Rectangle(
                    (j, 1 - i),
                    1,
                    1,
                    facecolor=cell_bg[i, j],
                    edgecolor="white",
                    linewidth=1.5,
                    zorder=1,
                )
            )
            x = j + 0.5
            y = 1.5 - i
            ax.text(
                x,
                y + 0.08,
                f"{int(matrix[i, j])}",
                ha="center",
                va="center",
                fontsize=13,
                fontweight="bold",
                color=cell_fg[i, j],
                zorder=2,
            )
            ax.text(
                x,
                y - 0.15,
                cell_labels[i, j],
                ha="center",
                va="center",
                fontsize=7.3,
                color=TEXT_COLOR,
                zorder=2,
            )
    ax.set_xticks([0.5, 1.5])
    ax.set_yticks([1.5, 0.5])
    ax.set_xticklabels(["Final correct", "Final wrong"], fontsize=7.5, color=MUTED_TEXT)
    ax.set_yticklabels(["Initial correct", "Initial wrong"], fontsize=7.5, color=MUTED_TEXT)
    ax.xaxis.tick_top()
    ax.tick_params(axis="both", length=0, pad=2)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(
        0.02,
        0.98,
        "Human-first correction matrix",
        ha="left",
        va="top",
        fontsize=8.8,
        fontweight="bold",
        color=TEXT_COLOR,
    )
    fig.tight_layout(rect=[0.04, 0.02, 1.0, 0.90])
    save_fig(fig, "human_first_correction_matrix.png", figures_dir, pad_inches=0.01)
    plt.close(fig)
    generated.append("human_first_correction_matrix.png")

    # Figure 3 — WOA distribution
    if len(w_all) == 0:
        print("WOA data unavailable — skipped woa_distribution.png")
    else:
        n_woa_valid = int(hf_counts["n_woa_valid"])
        n_no_adj_woa = int(hf_counts["n_no_adj_woa"])
        n_adj_woa = int(hf_counts["n_adj_woa"])
        median_adjusted = float(w_adj.median()) if len(w_adj) > 0 else float("nan")
        no_adjust_pct = n_no_adj_woa / n_woa_valid
        adjust_pct = n_adj_woa / n_woa_valid

        fig, axes = plt.subplots(1, 2, figsize=(6.7, 2.25), gridspec_kw={"width_ratios": [1.0, 2.25]})
        fig.patch.set_facecolor("white")
        ax0, ax1 = axes

        ax0.barh(0, no_adjust_pct, color=WOA_NO_MOVE_COLOR, height=0.34, edgecolor="white", linewidth=0.8)
        ax0.barh(0, adjust_pct, left=no_adjust_pct, color=COST_COLOR, height=0.34, edgecolor="white", linewidth=0.8)
        ax0.text(no_adjust_pct / 2, 0, f"{n_no_adj_woa}\n{no_adjust_pct:.1%}", ha="center", va="center", fontsize=7.2, fontweight="bold", color="white")
        ax0.text(no_adjust_pct + adjust_pct / 2, 0, f"{n_adj_woa}\n{adjust_pct:.1%}", ha="center", va="center", fontsize=7.2, fontweight="bold", color="white")
        ax0.text(no_adjust_pct / 2, -0.26, "No movement", ha="center", va="top", fontsize=7, color=MUTED_TEXT)
        ax0.text(no_adjust_pct + adjust_pct / 2, -0.26, "Adjusted", ha="center", va="top", fontsize=7, color=MUTED_TEXT)
        ax0.set_xlim(0, 1)
        ax0.set_ylim(-0.45, 0.45)
        ax0.set_yticks([])
        ax0.set_xticks([])
        ax0.set_title("(a) Adjustment incidence", loc="left", fontsize=8.5, fontweight="bold", color=TEXT_COLOR, pad=5)
        ax0.grid(False)
        for spine in ax0.spines.values():
            spine.set_visible(False)
        ax0.tick_params(axis="both", length=0)

        ax1.hist(w_adj, bins=np.linspace(-1, 2, 25), color=COST_COLOR, edgecolor="white", linewidth=0.45, alpha=0.95)
        ax1.axvline(median_adjusted, color=WOA_MEDIAN_COLOR, lw=1.4, linestyle="--")
        ax1.axvline(1, color=WOA_NO_MOVE_COLOR, lw=1.2, linestyle=":")
        ymax = ax1.get_ylim()[1]
        ax1.text(
            median_adjusted - 0.03,
            ymax * 0.88,
            f"Median = {median_adjusted:.3f}",
            ha="right",
            va="center",
            fontsize=7.2,
            fontweight="bold",
            color=WOA_MEDIAN_COLOR,
            bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor=WOA_MEDIAN_COLOR, linewidth=0.7),
        )
        ax1.text(1.03, ymax * 0.78, "WOA = 1", ha="left", va="center", fontsize=7.2, color=MUTED_TEXT)
        ax1.set_xlim(-1, 2)
        ax1.set_xlabel("Weight of Advice (WOA)", fontsize=7.5, color=MUTED_TEXT)
        ax1.set_ylabel("Adjusted trials", fontsize=7.5, color=MUTED_TEXT)
        ax1.set_title("(b) WOA among adjusted trials", loc="left", fontsize=8.5, fontweight="bold", color=TEXT_COLOR, pad=5)
        ax1.grid(False)
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)
        ax1.spines["left"].set_color(AXIS_COLOR)
        ax1.spines["bottom"].set_color(AXIS_COLOR)
        ax1.spines["left"].set_linewidth(0.6)
        ax1.spines["bottom"].set_linewidth(0.6)
        ax1.tick_params(axis="both", colors=MUTED_TEXT, labelsize=7, width=0.6, length=2.5)
        fig.tight_layout(w_pad=1.05)
        save_fig(fig, "woa_distribution.png", figures_dir, pad_inches=0.02)
        plt.close(fig)
        generated.append("woa_distribution.png")

    # Figure 4 — case risk vs mean trial cost
    if len(case_stats) == 0:
        print("case_stats unavailable — skipped case_risk_cost_scatter.png")
    else:
        fig, ax = plt.subplots(figsize=(4.15, 2.65))
        fig.patch.set_facecolor("white")
        for tier in TIERS:
            sub = case_stats[case_stats["difficulty_tier"] == tier]
            ax.scatter(
                sub["pred_prob"],
                sub["mean_cost"],
                color=TIER_COLORS[tier],
                label=tier.capitalize(),
                s=34,
                edgecolors="white",
                linewidths=0.5,
                alpha=0.95,
                zorder=3,
            )
        ax.axvline(TAU, color=TEXT_COLOR, linewidth=0.85, linestyle="--", alpha=0.8, zorder=2)
        ax.text(TAU + 0.015, 3.65, r"$\tau = 1/6$", fontsize=7.2, color=TEXT_COLOR, ha="left", va="center")
        ax.set_xlim(0, 1.0)
        ax.set_ylim(-0.05, 4.15)
        ax.set_xlabel("AI-predicted default probability", fontsize=7.6, color=MUTED_TEXT)
        ax.set_ylabel("Mean decision cost", fontsize=7.6, color=MUTED_TEXT)
        ax.set_title("Case-level risk and human cost", fontsize=8.6, fontweight="bold", loc="left", color=TEXT_COLOR, pad=6)
        ax.legend(
            frameon=False,
            fontsize=6.8,
            loc="upper right",
            bbox_to_anchor=(0.985, 0.985),
            ncol=1,
            handletextpad=0.25,
            labelspacing=0.25,
            borderaxespad=0.0,
            markerscale=0.85,
        )
        ax.grid(False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(AXIS_COLOR)
        ax.spines["bottom"].set_color(AXIS_COLOR)
        ax.spines["left"].set_linewidth(0.6)
        ax.spines["bottom"].set_linewidth(0.6)
        ax.tick_params(axis="both", colors=MUTED_TEXT, labelsize=7, width=0.6, length=2.5)
        fig.tight_layout(pad=0.45)
        save_fig(fig, "case_risk_cost_scatter.png", figures_dir, pad_inches=0.02)
        plt.close(fig)
        generated.append("case_risk_cost_scatter.png")

    # Figure 5 — normative deviation by difficulty
    fig, ax = plt.subplots(figsize=(3.45, 2.25))
    fig.patch.set_facecolor("white")
    x = np.arange(len(dev_by_tier))
    values = dev_by_tier["deviation_rate"].values
    bars = ax.bar(x, values, color=COST_COLOR, width=0.54, edgecolor="none")
    ax.set_xticks(x)
    ax.set_xticklabels([str(t).capitalize() for t in dev_by_tier["difficulty_tier"]], fontsize=8, color=TEXT_COLOR)
    ax.set_ylim(0, 0.82)
    ax.set_ylabel("Deviation rate", fontsize=7.8, color=MUTED_TEXT)
    ax.set_title("Deviation from cost-sensitive rule", loc="left", fontsize=8.8, fontweight="bold", color=TEXT_COLOR, pad=6)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.025,
            f"{value:.1%}",
            ha="center",
            va="bottom",
            fontsize=7.8,
            color=TEXT_COLOR,
            fontweight="bold",
        )
    ax.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(AXIS_COLOR)
    ax.spines["bottom"].set_color(AXIS_COLOR)
    ax.spines["left"].set_linewidth(0.6)
    ax.spines["bottom"].set_linewidth(0.6)
    ax.tick_params(axis="both", colors=MUTED_TEXT, labelsize=7, width=0.6, length=2.5)
    fig.tight_layout(pad=0.45)
    save_fig(fig, "normative_deviation_by_difficulty.png", figures_dir, pad_inches=0.02)
    plt.close(fig)
    generated.append("normative_deviation_by_difficulty.png")

    return generated


# ---------------------------------------------------------------------------
# Exports and final consistency checks
# ---------------------------------------------------------------------------

def export_compact_tables(
    scored_a: pd.DataFrame,
    pp_cost: pd.DataFrame,
    pp_acc: pd.DataFrame,
    cost_by_proto: pd.DataFrame,
    cost_rows: list[dict[str, Any]],
    acc_rows: list[dict[str, Any]],
    correction_table: pd.DataFrame,
    woa_summary: pd.DataFrame,
    case_stats: pd.DataFrame,
    tables_dir: Path = TABLES_DIR,
) -> list[str]:
    protocol_outcomes = pd.DataFrame(
        {
            "protocol": PROTOCOLS,
            "label": [PROTOCOL_LABELS[p] for p in PROTOCOLS],
            "mean_trial_cost": [float(pp_cost[p].mean()) for p in PROTOCOLS],
            "mean_accuracy": [float(pp_acc[p].mean()) for p in PROTOCOLS],
            "mean_optimal_cost": [float(cost_by_proto.loc[p, "opt_cost"]) for p in PROTOCOLS],
            "n_participants": [int(pp_cost[p].notna().sum()) for p in PROTOCOLS],
            "n_trials": [int((scored_a["protocol"] == p).sum()) for p in PROTOCOLS],
        }
    )
    protocol_contrasts = pd.concat(
        [
            contrast_dataframe(cost_rows, "trial_cost"),
            contrast_dataframe(acc_rows, "accuracy"),
        ],
        ignore_index=True,
    )

    protocol_outcomes.to_csv(tables_dir / "protocol_outcomes.csv", index=False)
    protocol_contrasts.to_csv(tables_dir / "protocol_contrasts.csv", index=False)
    correction_table.to_csv(tables_dir / "human_first_correction_matrix.csv")
    woa_summary.to_csv(tables_dir / "woa_summary.csv", index=False)
    case_stats.to_csv(tables_dir / "case_level_cost.csv", index=False)

    print("\n[Saved compact analysis tables]")
    for name in EXPECTED_TABLES:
        print(f"  - {rel(tables_dir / name)}")
    return EXPECTED_TABLES.copy()


def final_claim_checks(
    completed_ids: set[Any],
    scored_a: pd.DataFrame,
    pp_cost: pd.DataFrame,
    pp_acc: pd.DataFrame,
    cost_by_proto: pd.DataFrame,
    cost_rows: list[dict[str, Any]],
    acc_rows: list[dict[str, Any]],
    correction_table: pd.DataFrame,
    woa_summary: pd.DataFrame,
    w_adj: pd.Series,
    rho_case: float,
    p_rho_case: float,
) -> dict[str, Any]:
    print("\n" + "=" * 72)
    print("FINAL REPORTED RESULTS — COMPUTED CHECKS")
    print("=" * 72)

    cost_means = cost_by_proto["trial_cost"].to_dict()
    acc_means = pp_acc.mean().round(4).to_dict()

    r_cost_ai = paired_ttest(pp_cost, "no_ai", "ai_first")
    r_cost_hf = paired_ttest(pp_cost, "no_ai", "human_first")
    r_cost_timing = paired_ttest(pp_cost, "ai_first", "human_first")
    r_acc_ai = paired_ttest(pp_acc, "no_ai", "ai_first")
    r_acc_hf = paired_ttest(pp_acc, "no_ai", "human_first")
    r_acc_timing = paired_ttest(pp_acc, "ai_first", "human_first")

    g_stay_ok = int(correction_table.loc["Initial correct", "Final correct"])
    g_worsened = int(correction_table.loc["Initial correct", "Final wrong"])
    g_improved = int(correction_table.loc["Initial wrong", "Final correct"])
    g_stay_bad = int(correction_table.loc["Initial wrong", "Final wrong"])

    ws = woa_summary.iloc[0].to_dict()

    # Hard consistency checks for paper-reported values.
    assert len(completed_ids) == 100
    assert len(scored_a) == 1800
    assert np.isclose(cost_means["no_ai"], 1.2217, atol=0.0001)
    assert np.isclose(cost_means["ai_first"], 1.0117, atol=0.0001)
    assert np.isclose(cost_means["human_first"], 0.9233, atol=0.0001)
    assert np.isclose(acc_means["no_ai"], 0.5517, atol=0.0001)
    assert np.isclose(acc_means["ai_first"], 0.6350, atol=0.0001)
    assert np.isclose(acc_means["human_first"], 0.6500, atol=0.0001)
    assert (g_stay_ok, g_worsened, g_improved, g_stay_bad) == (300, 32, 90, 178)
    assert (int(ws["human_first_trials"]), int(ws["woa_valid"]), int(ws["no_adjustment"]), int(ws["adjusted_trials"])) == (600, 579, 304, 275)
    assert np.isclose(float(w_adj.median()), 0.869, atol=0.001)

    print("\nClaim 1: AI-supported protocols reduced decision cost relative to no AI")
    print(f"  No AI={cost_means['no_ai']:.4f} AI-first={cost_means['ai_first']:.4f} Human-first={cost_means['human_first']:.4f}")
    print(f"  No AI vs AI-first   : Δ={r_cost_ai['mean_diff']:+.4f} {fmt_p(r_cost_ai['p'])} d={r_cost_ai['d']}")
    print(f"  No AI vs Human-first: Δ={r_cost_hf['mean_diff']:+.4f} {fmt_p(r_cost_hf['p'])} d={r_cost_hf['d']}")

    print("\nClaim 2: Human-first was best descriptively, but not statistically decisive versus AI-first")
    print(f"  AI-first vs Human-first: Δ={r_cost_timing['mean_diff']:+.4f} {fmt_p(r_cost_timing['p'])} d={r_cost_timing['d']}")

    print("\nClaim 3: Accuracy follows the same ordering as cost")
    print(f"  No AI={acc_means['no_ai']:.4f} AI-first={acc_means['ai_first']:.4f} Human-first={acc_means['human_first']:.4f}")
    print(f"  No AI vs AI-first   : Δ={r_acc_ai['mean_diff']:+.4f} {fmt_p(r_acc_ai['p'])} d={r_acc_ai['d']}")
    print(f"  No AI vs Human-first: Δ={r_acc_hf['mean_diff']:+.4f} {fmt_p(r_acc_hf['p'])} d={r_acc_hf['d']}")
    print(f"  AI-first vs Human-first: Δ={r_acc_timing['mean_diff']:+.4f} {fmt_p(r_acc_timing['p'])} d={r_acc_timing['d']}")

    print("\nClaim 4: Human-first AI exposure corrected more initial errors than it introduced")
    print(f"  Improved={g_improved} Worsened={g_worsened} Net={g_improved - g_worsened:+d}")

    print("\nClaim 5: Reliance was heterogeneous")
    print(f"  {int(ws['woa_valid'])} WOA-valid trials: {int(ws['no_adjustment'])} no-adjustment ({int(ws['no_adjustment']) / int(ws['woa_valid']):.1%})")
    print(f"  Median WOA among adjusted trials (n={int(ws['adjusted_trials'])}) = {float(ws['adjusted_median']):.3f}")

    print("\nClaim 6: Case-level cost was not monotonically ordered by AI risk in the selected case set")
    print(f"  Spearman rho={rho_case:.3f} {fmt_p(p_rho_case)}")

    print("\nInterpretation boundary:")
    print("  AI support improved outcomes relative to no AI.")
    print("  The direct timing contrast between AI-first and human-first is not statistically decisive.")

    return {
        "completed_participants": len(completed_ids),
        "scored_trials": len(scored_a),
        "cost_means": {k: float(v) for k, v in cost_means.items()},
        "accuracy_means": {k: float(v) for k, v in acc_means.items()},
        "cost_contrasts": contrast_dataframe(cost_rows, "trial_cost").to_dict(orient="records"),
        "accuracy_contrasts": contrast_dataframe(acc_rows, "accuracy").to_dict(orient="records"),
        "human_first_correction_matrix": {
            "stayed_correct": g_stay_ok,
            "worsened": g_worsened,
            "improved": g_improved,
            "stayed_wrong": g_stay_bad,
        },
        "woa_summary": ws,
        "case_risk_cost_spearman": {"rho": rho_case, "p": p_rho_case},
    }


def write_summary_json(summary: dict[str, Any], out_path: Path) -> None:
    def convert(obj: Any) -> Any:
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if pd.isna(obj) if isinstance(obj, (float, np.floating)) else False:
            return None
        return obj

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=convert)
    print(f"\nSaved summary: {rel(out_path)}")


# ---------------------------------------------------------------------------
# Main entrypoint used by run.py
# ---------------------------------------------------------------------------

def run_paper_reproduction(output_dir: Path | None = None, exports_dir: Path | None = None) -> Path:
    # output_dir is accepted for compatibility with run.py. The official default
    # uses artifacts/tables and artifacts/figures to match the final repo layout.
    root_out = output_dir or ARTIFACTS_DIR
    tables_dir = ensure_dir(root_out / "tables")
    figures_dir = ensure_dir(root_out / "figures")
    exp_dir = exports_dir or EXPORTS_DIR

    print("=" * 72)
    print("CAPSTONE PAPER REPRODUCTION")
    print("Analysis logic: codes/notebooks/analysis.ipynb, non-notebook version")
    print("=" * 72)
    print(f"ROOT         : {ROOT}")
    print(f"EXPORTS_DIR  : {exp_dir}")
    print(f"FROZEN_DIR   : {FROZEN_DIR}")
    print(f"TABLES_DIR   : {tables_dir}")
    print(f"FIGURES_DIR  : {figures_dir}")
    print("Raw loan.csv : not required for default reproduction")

    ensure_dir(tables_dir)
    ensure_dir(figures_dir)
    clean_previous_outputs(tables_dir, figures_dir)

    print("\n[Validation]")
    validate_frozen_artifacts(FROZEN_DIR)
    print("Frozen artifacts: OK")

    participants_raw, trials_raw, quiz_raw = load_exports(exp_dir)
    participants_a, scored_a, completed_ids = build_analysis_sample(participants_raw, trials_raw)
    scored_a = add_derived_variables(scored_a)

    pp_cost, cost_by_proto, cost_rows = analyze_primary_cost(scored_a)
    pp_acc, acc_rows = analyze_accuracy(scored_a)
    correction_table, woa_summary, w_all, w_adj, hf_counts = analyze_human_first(scored_a)
    case_stats, rho_case, p_rho_case = analyze_case_level(scored_a)
    dev_by_tier = analyze_normative_deviation(scored_a)

    print("\n[Export]")
    tables = export_compact_tables(
        scored_a,
        pp_cost,
        pp_acc,
        cost_by_proto,
        cost_rows,
        acc_rows,
        correction_table,
        woa_summary,
        case_stats,
        tables_dir=tables_dir,
    )

    print("\n[Figures]")
    figures = make_figures(
        pp_cost,
        pp_acc,
        correction_table,
        w_all,
        w_adj,
        hf_counts,
        case_stats,
        dev_by_tier,
        figures_dir=figures_dir,
    )

    headline = final_claim_checks(
        completed_ids,
        scored_a,
        pp_cost,
        pp_acc,
        cost_by_proto,
        cost_rows,
        acc_rows,
        correction_table,
        woa_summary,
        w_adj,
        rho_case,
        p_rho_case,
    )

    summary = {
        "mode": "paper",
        "logic_source": "codes/notebooks/analysis.ipynb",
        "inputs": {
            "experiment_exports_dir": rel(exp_dir),
            "frozen_artifacts_dir": rel(FROZEN_DIR),
            "raw_data_required": False,
        },
        "outputs": {
            "tables_dir": rel(tables_dir),
            "figures_dir": rel(figures_dir),
            "tables": tables,
            "figures": figures,
            "figure_format": "png only",
        },
        "headline": headline,
    }
    write_summary_json(summary, root_out / "summary.json")

    print("\n[Done]")
    print(f"Compact tables written : {len(tables)}")
    print(f"Figures written        : {len(figures)}")
    print(f"Output root            : {root_out}")
    return root_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce final paper results without requiring raw loan.csv.")
    parser.add_argument("--output-dir", default=str(ARTIFACTS_DIR), help="Output root. Default: artifacts/.")
    parser.add_argument("--exports-dir", default=str(EXPORTS_DIR), help="Directory containing Supabase exports.")
    args = parser.parse_args()
    out = run_paper_reproduction(output_dir=Path(args.output_dir), exports_dir=Path(args.exports_dir))
    print(f"Paper reproduction outputs written to {out}")


if __name__ == "__main__":
    main()