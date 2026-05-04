from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import binomtest

PROTOCOLS = ["no_ai", "ai_first", "human_first"]
PROTOCOL_LABELS = {
    "no_ai": "No AI",
    "ai_first": "AI-first",
    "human_first": "Human-first",
}
TIERS = ["easy", "medium", "hard"]
TAU = 1 / 6
C_FN = 5
C_FP = 1


def trial_cost(decision: int, y_true: int, c_fn: int = C_FN, c_fp: int = C_FP) -> int:
    """Decision convention: 1=approve, 0=reject. y_true: 1=default, 0=paid."""
    if int(decision) == 1 and int(y_true) == 1:
        return c_fn
    if int(decision) == 0 and int(y_true) == 0:
        return c_fp
    return 0


def brier_score(y_true: Iterable[float], prob: Iterable[float]) -> float:
    y = np.asarray(list(y_true), dtype=float)
    p = np.asarray(list(prob), dtype=float)
    mask = np.isfinite(y) & np.isfinite(p)
    if mask.sum() == 0:
        return np.nan
    return float(np.mean((p[mask] - y[mask]) ** 2))


def paired_ttest_from_wide(wide: pd.DataFrame, a: str, b: str) -> dict:
    if a not in wide.columns or b not in wide.columns:
        return {"n": 0, "mean_diff": np.nan, "t": np.nan, "p": np.nan, "ci_low": np.nan, "ci_high": np.nan}
    d = wide[[a, b]].dropna().copy()
    if len(d) < 2:
        return {"n": len(d), "mean_diff": np.nan, "t": np.nan, "p": np.nan, "ci_low": np.nan, "ci_high": np.nan}
    diff = d[a] - d[b]
    t, p = stats.ttest_rel(d[a], d[b])
    ci = stats.t.interval(0.95, df=len(d) - 1, loc=diff.mean(), scale=diff.sem())
    return {
        "n": int(len(d)),
        "mean_diff": float(diff.mean()),
        "t": float(t),
        "p": float(p),
        "ci_low": float(ci[0]),
        "ci_high": float(ci[1]),
        "cohens_dz": float(diff.mean() / diff.std(ddof=1)) if diff.std(ddof=1) != 0 else np.nan,
    }


def format_p(p: float) -> str:
    if pd.isna(p):
        return "—"
    if p < 0.0001:
        return "p < .0001"
    return f"p = {p:.4f}"


def protocol_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for proto in PROTOCOLS:
        d = df[df["protocol"] == proto].copy()
        if d.empty:
            continue
        rows.append(
            {
                "protocol": proto,
                "Protocol": PROTOCOL_LABELS.get(proto, proto),
                "N trials": len(d),
                "Participants": d["participant_id"].nunique(),
                "Accuracy": d["correct"].mean(),
                "Mean cost": d["trial_cost"].mean(),
                "Excess cost": d["cost_excess"].mean(),
                "Brier": brier_score(d["y_true"], d["prob_estimate_final"]),
                "AI distance": d["prob_dist"].mean(),
                "Approval rate": d["decision_final"].mean(),
                "Median RT (s)": d["total_trial_ms"].median() / 1000 if "total_trial_ms" in d else np.nan,
            }
        )
    return pd.DataFrame(rows)


def protocol_participant_wide(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    return df.groupby(["participant_id", "protocol"])[metric].mean().unstack("protocol")


def pairwise_protocol_tests(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    wide = protocol_participant_wide(df, metric)
    pairs = [("no_ai", "ai_first"), ("no_ai", "human_first"), ("ai_first", "human_first")]
    rows = []
    for a, b in pairs:
        res = paired_ttest_from_wide(wide, a, b)
        rows.append({
            "Comparison": f"{PROTOCOL_LABELS[a]} − {PROTOCOL_LABELS[b]}",
            "Mean diff": res["mean_diff"],
            "95% CI": f"[{res['ci_low']:.3f}, {res['ci_high']:.3f}]" if np.isfinite(res["ci_low"]) else "—",
            "t": res["t"],
            "p": res["p"],
            "N": res["n"],
        })
    return pd.DataFrame(rows)


def human_first_switches(df: pd.DataFrame) -> dict:
    h = df[df["protocol"] == "human_first"].dropna(subset=["decision_init", "decision_final", "y_true"]).copy()
    if h.empty:
        return {"n": 0, "matrix": pd.DataFrame(), "summary": pd.DataFrame(), "sign_p": np.nan}
    h["correct_init"] = (((h["decision_init"] == 1) & (h["y_true"] == 0)) | ((h["decision_init"] == 0) & (h["y_true"] == 1))).astype(int)
    h["correct_final"] = (((h["decision_final"] == 1) & (h["y_true"] == 0)) | ((h["decision_final"] == 0) & (h["y_true"] == 1))).astype(int)
    h["initial_state"] = np.where(h["correct_init"] == 1, "Initial correct", "Initial wrong")
    h["final_state"] = np.where(h["correct_final"] == 1, "Final correct", "Final wrong")

    matrix = pd.crosstab(h["initial_state"], h["final_state"]).reindex(
        index=["Initial correct", "Initial wrong"], columns=["Final correct", "Final wrong"], fill_value=0
    )

    stayed_correct = int(matrix.loc["Initial correct", "Final correct"])
    worsened = int(matrix.loc["Initial correct", "Final wrong"])
    improved = int(matrix.loc["Initial wrong", "Final correct"])
    stayed_wrong = int(matrix.loc["Initial wrong", "Final wrong"])
    switchers = improved + worsened
    sign_p = float(binomtest(improved, switchers, 0.5).pvalue) if switchers else np.nan
    summary = pd.DataFrame(
        [
            {"Path": "Stayed correct", "Count": stayed_correct, "Percent": stayed_correct / len(h)},
            {"Path": "Improved wrong → correct", "Count": improved, "Percent": improved / len(h)},
            {"Path": "Stayed wrong", "Count": stayed_wrong, "Percent": stayed_wrong / len(h)},
            {"Path": "Worsened correct → wrong", "Count": worsened, "Percent": worsened / len(h)},
        ]
    )
    return {
        "n": int(len(h)),
        "matrix": matrix,
        "summary": summary,
        "improved": improved,
        "worsened": worsened,
        "net_gain": improved - worsened,
        "sign_p": sign_p,
        "data": h,
    }


def woa_summary(df: pd.DataFrame) -> dict:
    h = df[(df["protocol"] == "human_first") & df["prob_estimate_init"].notna()].copy()
    if h.empty or "woa" not in h:
        return {"n": 0}
    w = h["woa"].dropna()
    if w.empty:
        return {"n": 0}
    adjusters = w[w.abs() >= 0.01]
    return {
        "n": int(len(w)),
        "mean": float(w.mean()),
        "median": float(w.median()),
        "sd": float(w.std(ddof=1)),
        "zero_n": int((w == 0).sum()),
        "zero_pct": float((w == 0).mean()),
        "adjuster_n": int(len(adjusters)),
        "adjuster_pct": float(len(adjusters) / len(w)),
        "adjuster_mean": float(adjusters.mean()) if len(adjusters) else np.nan,
        "adjuster_median": float(adjusters.median()) if len(adjusters) else np.nan,
        "data": h.dropna(subset=["woa"]),
    }


def reliance_decomposition(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["protocol"].isin(["ai_first", "human_first"])].copy()
    if d.empty:
        return pd.DataFrame()
    for col in ["ai_rec", "ai_correct", "follows_ai"]:
        if col not in d.columns:
            return pd.DataFrame()
    # Internal column keys kept for backward compatibility with charts.py display_names mapping.
    d["Beneficial reliance"] = ((d["follows_ai"] == 1) & (d["ai_correct"] == 1)).astype(int)
    d["Over-reliance"] = ((d["follows_ai"] == 1) & (d["ai_correct"] == 0)).astype(int)
    d["Beneficial override"] = ((d["follows_ai"] == 0) & (d["ai_correct"] == 0)).astype(int)
    d["Harmful override"] = ((d["follows_ai"] == 0) & (d["ai_correct"] == 1)).astype(int)
    cols = ["Beneficial reliance", "Over-reliance", "Beneficial override", "Harmful override"]
    out = d.groupby("protocol")[cols].mean().reset_index()
    out["Protocol"] = out["protocol"].map(PROTOCOL_LABELS)
    return out


def case_summary(df: pd.DataFrame) -> pd.DataFrame:
    if "case_id" not in df.columns:
        return pd.DataFrame()
    rows = []
    for case_id, c in df.groupby("case_id", dropna=False):
        row = {
            "case_id": case_id,
            "case_position": c["case_position"].iloc[0] if "case_position" in c.columns else np.nan,
            "difficulty_tier": c["difficulty_tier"].iloc[0] if "difficulty_tier" in c.columns else None,
            "pred_prob": c["pred_prob"].iloc[0] if "pred_prob" in c.columns else np.nan,
            "y_true": c["y_true"].iloc[0] if "y_true" in c.columns else np.nan,
            "optimal_dec": c["optimal_dec"].iloc[0] if "optimal_dec" in c.columns else np.nan,
            "n_trials": len(c),
            "accuracy": c["correct"].mean(),
            "mean_cost": c["trial_cost"].mean(),
            "approve_rate": c["decision_final"].mean(),
        }
        for proto in PROTOCOLS:
            p = c[c["protocol"] == proto]
            row[f"accuracy_{proto}"] = p["correct"].mean() if len(p) else np.nan
            row[f"cost_{proto}"] = p["trial_cost"].mean() if len(p) else np.nan
            row[f"approve_{proto}"] = p["decision_final"].mean() if len(p) else np.nan
        rows.append(row)
    out = pd.DataFrame(rows)
    if "case_position" in out.columns:
        out = out.sort_values(["case_position", "case_id"], na_position="last")
    return out
