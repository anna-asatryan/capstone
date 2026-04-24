# Architecture

## Products

### Experiment platform

- Path: `codes/experiment_platform/`
- Framework: Streamlit
- Purpose: participant-facing behavioral experiment
- Standalone repo: `capstone-experiment-platform` (synced via GitHub Actions)

### Summary app

- Path: `codes/summary_app/`
- Framework: Dash + Plotly
- Purpose: post-study results dashboard for poster/demo
- Input: `artifacts/analysis/latest/`
- Standalone repo: `capstone-analysis-app` (synced after participant data collected)

## Notebook pipeline

| Notebook | Inputs | Outputs |
|---|---|---|
| `codes/notebooks/eda.ipynb` | `data/raw/loan.csv` | `data/processed/loan_v1.csv` |
| `codes/notebooks/modeling.ipynb` | `data/processed/loan_v1.csv` | `artifacts/test_predictions.parquet` |
| `codes/notebooks/case_design.ipynb` | `artifacts/frozen/candidate_pool_scored.parquet` | `artifacts/frozen/` (locked) |

`case_design.ipynb` reads from the frozen candidate pool, not from the regeneratable `test_predictions.parquet`, so re-running upstream notebooks cannot silently change which cases participants see.

## Pipelines

### `codes/pipelines/validate_artifacts.py`

Validates the official frozen boundary:
- required files exist
- hashes match `cases.lock.json`
- manifest hashes match
- expected row counts and required columns present

### `codes/pipelines/reproduce_from_frozen.py`

Official deterministic path. Reads from `artifacts/frozen/`, writes to `artifacts/analysis/latest/`.

### `codes/pipelines/rebuild_from_upstream.py`

Best-effort upstream rebuild. Reads `data/raw/loan.csv` and current feature engineering logic. Writes intermediates to `artifacts/rebuild/`, then shared downstream bundle to `artifacts/analysis/latest/`.

### `codes/pipelines/common.py`

Shared helpers:
- hashing and manifest utilities
- candidate-pool enrichment (`enrich_candidate_pool()`)
- model metrics and calibration summaries
- case-cost and protocol summaries
- analysis bundle writing
- participant export summaries (used once Supabase CSVs land in `artifacts/frozen/experiment_exports/`)

## CLI

`run.py` at repo root is the canonical entrypoint.

```
python run.py [--mode frozen|rebuild|validate|doctor] [--launch-summary|--no-launch-summary]
```

Default mode is `frozen`. Helper modes (`validate`, `doctor`) return without launching the summary app.

## Frozen artifact policy

Exact reproducibility begins at the frozen candidate-pool and case-selection boundary, not merely at `final_cases.csv`. The locked boundary includes:

- selected cases and practice cases
- protocol rotation
- scored candidate pool used for selection
- manifest with parameters, hashes, and commit metadata
- lock file for the official deterministic bundle

## Summary app data contract

Reads from `artifacts/analysis/latest/`:

- `summary.json`
- `tables/model_metrics.csv`
- `tables/calibration_bins.csv`
- `tables/difficulty_summary.csv`
- `tables/selection_cells.csv`
- `tables/case_costs.csv`
- `tables/protocol_design.csv`
- `tables/final_cases.csv`
- `tables/practice_cases.csv`

Optional participant export tables (added after study without changing the app contract):

- `tables/participant_protocol_summary.csv`
- `tables/participant_reliance_summary.csv`
