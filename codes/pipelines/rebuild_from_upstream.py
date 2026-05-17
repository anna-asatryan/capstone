from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from codes.data_prep import build_features, load_and_clean
from codes.feature_config import CAT_COLS, FEATURES, NUM_COLS, TARGET
from codes.pipelines.common import (
    FROZEN_ARTIFACTS_DIR,
    RAW_DATA_PATH,
    REBUILD_DIR,
    TAU,
    enrich_candidate_pool,
    git_commit_hash,
    load_frozen_tables,
    sha256_file,
    write_json,
)


def apply_training_bins(df: pd.DataFrame, train: pd.DataFrame) -> pd.DataFrame:
    bin_edges: dict[str, list[float]] = {}

    for name, column, quantiles in [
        ("income", "log_annual_inc", 5),
        ("loan", "loan_amnt", 4),
        ("rate", "int_rate", 4),
        ("dti", "dti", 4),
    ]:
        _, edges = pd.qcut(train[column], q=quantiles, retbins=True, duplicates="drop")
        bin_edges[name] = list(edges)

    def open_edges(edges: list[float]) -> list[float]:
        mutable = list(edges)
        mutable[0] = float("-inf")
        mutable[-1] = float("inf")
        return mutable

    out = df.copy()
    out["income_bin"] = pd.cut(
        out["log_annual_inc"],
        bins=open_edges(bin_edges["income"]),
        include_lowest=True,
    )
    out["loan_bin"] = pd.cut(
        out["loan_amnt"],
        bins=open_edges(bin_edges["loan"]),
        include_lowest=True,
    )
    out["rate_bin"] = pd.cut(
        out["int_rate"],
        bins=open_edges(bin_edges["rate"]),
        include_lowest=True,
    )
    out["dti_bin"] = pd.cut(
        out["dti"],
        bins=open_edges(bin_edges["dti"]),
        include_lowest=True,
    )
    return out


def attach_difficulty(df: pd.DataFrame) -> pd.DataFrame:
    train = df[df["issue_d"] < "2016-01-01"].copy()
    scored = apply_training_bins(df, train)
    scored_train = scored[scored["issue_d"] < "2016-01-01"].copy()

    bin_cols = ["rate_bin", "dti_bin", "income_bin"]
    global_mean = float(scored_train[TARGET].mean())
    alpha = 50

    bin_stats = (
        scored_train
        .groupby(bin_cols, observed=True)
        .agg(bin_count=(TARGET, "size"), bin_mean=(TARGET, "mean"))
    )
    bin_stats["smoothed_rate"] = (
        (bin_stats["bin_count"] * bin_stats["bin_mean"] + alpha * global_mean)
        / (bin_stats["bin_count"] + alpha)
    )

    index = pd.MultiIndex.from_frame(scored[bin_cols])
    scored["case_base_rate"] = index.map(bin_stats["smoothed_rate"]).fillna(global_mean)
    scored["difficulty_score"] = (
        1 - (scored["case_base_rate"] - 0.5).abs() / 0.5
    ).clip(0, 1)
    scored["difficulty_tier"] = pd.cut(
        scored["difficulty_score"],
        bins=[0, 0.33, 0.66, 1],
        labels=["easy", "medium", "hard"],
        include_lowest=True,
    )

    scored = scored.dropna(
        subset=FEATURES + [TARGET, "difficulty_score", "difficulty_tier"]
    ).reset_index(drop=True)
    scored["case_id"] = scored.index.astype(int)

    return scored


def build_logistic_predictions(df: pd.DataFrame) -> pd.DataFrame:
    try:
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import brier_score_loss
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
    except Exception as exc:
        raise RuntimeError(
            "The rebuild path needs scikit-learn. Install the root requirements first."
        ) from exc

    train_full = df[df["issue_d"] < "2016-01-01"].copy()
    test = df[df["issue_d"] >= "2016-01-01"].copy()

    cutoff_cal = train_full["issue_d"].quantile(0.70)
    train = train_full[train_full["issue_d"] < cutoff_cal].copy()
    cal_val = train_full[train_full["issue_d"] >= cutoff_cal].copy()

    cutoff_val = cal_val["issue_d"].quantile(0.50)
    cal = cal_val[cal_val["issue_d"] < cutoff_val].copy()
    val = cal_val[cal_val["issue_d"] >= cutoff_val].copy()

    x_train = train[FEATURES].copy()
    x_cal = cal[FEATURES].copy()
    x_val = val[FEATURES].copy()
    x_test = test[FEATURES].copy()

    dti_upper = x_train["dti"].quantile(0.999)
    for frame in [x_train, x_cal, x_val, x_test]:
        frame["dti"] = frame["dti"].clip(upper=dti_upper)

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                NUM_COLS,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "onehot",
                            OneHotEncoder(
                                drop="first",
                                handle_unknown="ignore",
                                sparse_output=False,
                            ),
                        ),
                    ]
                ),
                CAT_COLS,
            ),
        ]
    )

    base_model = Pipeline(
        [
            ("preprocessor", preprocessor),
            ("model", LogisticRegression(C=0.1, max_iter=3000, random_state=42)),
        ]
    )
    base_model.fit(x_train, train[TARGET])

    isotonic = CalibratedClassifierCV(base_model, method="isotonic", cv="prefit")
    sigmoid = CalibratedClassifierCV(base_model, method="sigmoid", cv="prefit")
    isotonic.fit(x_cal, cal[TARGET])
    sigmoid.fit(x_cal, cal[TARGET])

    val_iso = isotonic.predict_proba(x_val)[:, 1]
    val_sig = sigmoid.predict_proba(x_val)[:, 1]

    selected = (
        isotonic
        if brier_score_loss(val[TARGET], val_iso) < brier_score_loss(val[TARGET], val_sig)
        else sigmoid
    )
    test_probs = selected.predict_proba(x_test)[:, 1]

    test_output = x_test.copy()
    test_output["case_id"] = test["case_id"].values
    test_output["y_true"] = test[TARGET].values
    test_output["pred_prob"] = test_probs
    test_output = test_output.merge(
        test[["case_id", "difficulty_score", "difficulty_tier"]],
        on="case_id",
        how="left",
    )

    ordered_columns = [
        "case_id",
        *FEATURES,
        "y_true",
        "pred_prob",
        "difficulty_score",
        "difficulty_tier",
    ]
    return enrich_candidate_pool(test_output[ordered_columns])


def sample_cell(
    df: pd.DataFrame,
    tier: str,
    correct: int,
    n: int,
    already_selected_probs: list[float] | None = None,
    min_dist: float = 0.02,
) -> pd.DataFrame:
    subset = df[(df["difficulty_tier"] == tier) & (df["correct"] == correct)].copy()

    if len(subset) <= n:
        return subset

    selected_probs = list(already_selected_probs or [])

    if tier == "hard":
        subset = subset.sort_values("pred_prob", ascending=False)
    elif tier == "easy" and correct == 1:
        subset = subset.sort_values("pred_prob", ascending=True)
    elif subset["model_optimal"].nunique() > 1:
        subset = subset.sort_values(["model_optimal", "pred_prob"])
    else:
        subset = subset.sort_values("pred_prob")

    selected_rows = []
    used_purposes: set[str] = set()

    for _, row in subset.iterrows():
        probability = row["pred_prob"]
        if any(abs(probability - prev) < min_dist for prev in selected_probs):
            continue

        if row["purpose"] not in used_purposes or len(selected_rows) < n:
            selected_rows.append(row)
            selected_probs.append(probability)
            used_purposes.add(str(row["purpose"]))

        if len(selected_rows) >= n:
            break

    if len(selected_rows) < n:
        remaining = subset.drop(index=[row.name for row in selected_rows], errors="ignore")
        for _, row in remaining.iterrows():
            probability = row["pred_prob"]
            if any(abs(probability - prev) < min_dist for prev in selected_probs):
                continue

            selected_rows.append(row)
            selected_probs.append(probability)

            if len(selected_rows) >= n:
                break

    if len(selected_rows) < n:
        remaining = subset.drop(index=[row.name for row in selected_rows], errors="ignore")
        for _, row in remaining.sample(frac=1, random_state=42).iterrows():
            selected_rows.append(row)

            if len(selected_rows) >= n:
                break

    return pd.DataFrame(selected_rows)


def select_cases(candidate_pool: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    filtered = candidate_pool[
        (candidate_pool["pred_prob"] > 0.05)
        & (candidate_pool["pred_prob"] < 0.95)
        & (candidate_pool["difficulty_tier"].notna())
        & (candidate_pool["purpose"] != "other")
    ].copy()

    cells = [
        ("easy", 1),
        ("hard", 1),
        ("hard", 0),
        ("medium", 1),
        ("medium", 0),
        ("easy", 0),
    ]

    selected_parts = []
    selected_probs: list[float] = []

    for tier, correct in cells:
        sample = sample_cell(filtered, tier, correct, 3, selected_probs)
        if len(sample) != 3:
            raise RuntimeError(
                f"Could not select 3 cases for cell difficulty={tier}, correct={correct}."
            )

        selected_parts.append(sample)
        selected_probs.extend(sample["pred_prob"].tolist())

    cases = pd.concat(selected_parts, ignore_index=True)
    block_labels = ["block_1", "block_2", "block_3"]
    assignments: list[pd.Series] = []

    for (_, _), group in cases.groupby(["difficulty_tier", "correct"], observed=True):
        shuffled = group.sample(frac=1, random_state=42).reset_index(drop=True)

        for index, block_name in enumerate(block_labels):
            row = shuffled.iloc[index].copy()
            row["block"] = block_name
            assignments.append(row)

    final_cases = pd.DataFrame(assignments).reset_index(drop=True)
    final_cases = final_cases.sort_values(
        ["block", "difficulty_tier", "correct"]
    ).reset_index(drop=True)
    final_cases["case_position"] = range(1, len(final_cases) + 1)

    selected_case_ids = set(cases["case_id"].astype(int).tolist())

    practice_safe = filtered[
        (~filtered["case_id"].isin(selected_case_ids))
        & (filtered["y_true"] == 0)
        & (filtered["pred_prob"] < 0.06)
        & (filtered["difficulty_tier"] == "easy")
    ].sample(1, random_state=42)

    practice_risky = filtered[
        (~filtered["case_id"].isin(selected_case_ids))
        & (filtered["y_true"] == 1)
        & (filtered["pred_prob"] > 0.55)
        & (filtered["difficulty_tier"] == "hard")
    ].sample(1, random_state=42)

    practice_cases = pd.concat([practice_safe, practice_risky], ignore_index=True)
    practice_cases["case_position"] = [-2, -1]
    practice_cases["block"] = "practice"

    protocol_rotation = pd.DataFrame(
        {
            "participant_group": ["group_1", "group_2", "group_3"],
            "block_1_protocol": ["no_ai", "human_first", "ai_first"],
            "block_2_protocol": ["human_first", "ai_first", "no_ai"],
            "block_3_protocol": ["ai_first", "no_ai", "human_first"],
            "target_n": [33, 33, 34],
        }
    )

    return enrich_candidate_pool(final_cases), enrich_candidate_pool(practice_cases), {
        "protocol_rotation": protocol_rotation,
        "filtered_candidate_pool_rows": int(len(filtered)),
    }


def write_rebuild_manifest(
    output_dir: Path,
    candidate_pool_path: Path,
    final_cases_path: Path,
    practice_cases_path: Path,
    protocol_rotation_path: Path,
    exact_case_match: bool,
) -> dict:
    manifest = {
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "rebuild",
        "git_commit": git_commit_hash(),
        "source_files": [str(RAW_DATA_PATH)],
        "exact_rebuild_guaranteed": False,
        "exact_case_match_to_official_frozen": exact_case_match,
        "seeds": {
            "global_numpy_seed": 42,
            "selection_random_state": 42,
        },
        "selection_parameters": {
            "candidate_filter": {
                "pred_prob_min_exclusive": 0.05,
                "pred_prob_max_exclusive": 0.95,
                "exclude_purpose": "other",
            },
            "per_cell": 3,
            "min_probability_distance": 0.02,
            "difficulty_thresholds": [0.33, 0.66],
            "difficulty_smoothing_alpha": 50,
            "tau": TAU,
        },
        "artifacts": {
            path.name: {"sha256": sha256_file(path)}
            for path in [
                candidate_pool_path,
                final_cases_path,
                practice_cases_path,
                protocol_rotation_path,
            ]
        },
        "notes": [
            "This path rebuilds from upstream inputs using the current scripted approximation of the notebooks.",
            "Exact identity with the official frozen paper cases is best-effort only because the original upstream selection workflow was not fully serialized.",
            "Official paper analysis uses artifacts/frozen/ and data/experiment_exports/, not artifacts/build/.",
        ],
    }

    write_json(output_dir / "selection_manifest.json", manifest)
    return manifest


def run_rebuild_from_upstream(
    rebuild_artifacts_dir: Path | None = None,
) -> Path:
    raw_path = RAW_DATA_PATH

    if not raw_path.exists():
        raise RuntimeError(
            "Raw data file not found. Rebuild mode needs the untracked LendingClub CSV at:\n"
            f"  {raw_path}\n\n"
            "Default reproduction does not need this file. To run rebuild, download the raw data, "
            "place it at data/raw/loan.csv, and rerun: python run.py --mode rebuild"
        )

    rebuild_dir = rebuild_artifacts_dir or REBUILD_DIR
    rebuild_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("OPTIONAL UPSTREAM REBUILD")
    print("=" * 72)
    print(f"raw data              : {raw_path}")
    print(f"rebuild output dir    : {rebuild_dir}")
    print("official frozen dir   : artifacts/frozen  [read-only]")
    print()
    print("[1/6] Loading and cleaning raw LendingClub data...")
    df = load_and_clean(raw_path)
    print(f"      rows after cleaning: {len(df):,}")

    print("[2/6] Building model features...")
    df = build_features(df)
    print(f"      rows with features: {len(df):,}")

    print("[3/6] Attaching difficulty bins...")
    df = attach_difficulty(df)

    print("[4/6] Training/scoring calibrated logistic model...")
    candidate_pool = build_logistic_predictions(df)
    print(f"      candidate pool rows: {len(candidate_pool):,}")

    print("[5/6] Selecting rebuilt experimental/practice cases...")
    final_cases, practice_cases, extras = select_cases(candidate_pool)
    protocol_rotation = extras["protocol_rotation"]
    print(f"      final cases   : {len(final_cases)}")
    print(f"      practice cases: {len(practice_cases)}")

    candidate_pool_path = rebuild_dir / "candidate_pool_scored.parquet"
    final_cases_path = rebuild_dir / "final_cases.csv"
    practice_cases_path = rebuild_dir / "practice_cases.csv"
    protocol_rotation_path = rebuild_dir / "protocol_rotation.csv"

    print("[6/6] Writing rebuild artifacts...")
    candidate_pool.to_parquet(candidate_pool_path, index=False)
    final_cases.to_csv(final_cases_path, index=False)
    practice_cases.to_csv(practice_cases_path, index=False)
    protocol_rotation.to_csv(protocol_rotation_path, index=False)

    print(f"      wrote: {candidate_pool_path}")
    print(f"      wrote: {final_cases_path}")
    print(f"      wrote: {practice_cases_path}")
    print(f"      wrote: {protocol_rotation_path}")

    frozen_tables = load_frozen_tables(FROZEN_ARTIFACTS_DIR)
    frozen_case_ids = set(frozen_tables["final_cases"]["case_id"].astype(int).tolist())
    rebuilt_case_ids = set(final_cases["case_id"].astype(int).tolist())
    exact_case_match = frozen_case_ids == rebuilt_case_ids

    write_rebuild_manifest(
        rebuild_dir,
        candidate_pool_path,
        final_cases_path,
        practice_cases_path,
        protocol_rotation_path,
        exact_case_match=exact_case_match,
    )

    print()
    print(f"      exact case-id match to frozen artifacts: {exact_case_match}")

    if not exact_case_match:
        print("      WARNING: rebuilt case identities differ from artifacts/frozen/.")
        print("      This is acceptable for provenance; official paper results still use frozen artifacts.")

    print()
    print("      Rebuild mode wrote upstream artifacts only.")
    print("      Official paper outputs are generated separately by: python run.py")

    return rebuild_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Best-effort rebuild from upstream inputs."
    )
    parser.add_argument(
        "--rebuild-artifacts-dir",
        type=Path,
        default=REBUILD_DIR,
        help="Directory where best-effort rebuild artifacts should be written.",
    )
    args = parser.parse_args()

    output_dir = run_rebuild_from_upstream(
        rebuild_artifacts_dir=args.rebuild_artifacts_dir,
    )
    print(f"Rebuild artifacts written to {output_dir}")


if __name__ == "__main__":
    main()