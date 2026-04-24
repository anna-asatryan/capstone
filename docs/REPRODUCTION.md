# Reproduction Guide

## Commands

```bash
# Default: deterministic reproduction from locked artifacts
python run.py --mode frozen --no-launch-summary

# Best-effort rebuild from raw data
python run.py --mode rebuild --no-launch-summary

# Validate frozen artifact hashes only
python run.py --mode validate

# Environment + artifact check
python run.py --mode doctor

# Launch the summary app against most recent pipeline outputs
python -m codes.summary_app.app

# Run the experiment platform locally
cd codes/experiment_platform && streamlit run app.py
```

## What each mode does

### Frozen mode (default)

Official deterministic reproduction path.

1. Validates `artifacts/frozen/` against `cases.lock.json`
2. Loads the frozen scored candidate pool and selected cases
3. Regenerates downstream analysis tables in `artifacts/analysis/latest/`
4. Prepares the Dash summary app data bundle
5. Optionally launches the summary app

Does not require a live Supabase database or raw data.

### Rebuild mode

Best-effort re-run from upstream inputs.

1. Reads `data/raw/loan.csv`
2. Rebuilds cleaned features and model-independent difficulty tiers
3. Retrains the scripted logistic + calibration pipeline
4. Reconstructs a scored candidate pool and selects cases using extracted notebook heuristics
5. Compares rebuilt case identities against the official frozen set
6. Continues into the same downstream analysis flow

Exact identity with the official paper cases is not guaranteed — the original upstream notebooks did not serialize every stochastic step.

## Frozen boundary

```
artifacts/frozen/
  final_cases.csv
  practice_cases.csv
  protocol_rotation.csv
  candidate_pool_scored.parquet
  selection_manifest.json
  cases.lock.json
```

If any locked file is missing or its hash changes, validation fails loudly.

## Output locations

Downstream pipeline outputs (generated on each run, gitignored):

```
artifacts/analysis/latest/summary.json
artifacts/analysis/latest/tables/*.csv
```

Best-effort rebuild intermediates (generated on rebuild, gitignored):

```
artifacts/rebuild/
```

## Deterministic vs best-effort

Truly deterministic:
- Frozen artifact validation
- Downstream summaries computed from the frozen candidate pool and case set
- Summary app rendering from generated analysis tables

Best-effort only:
- Rebuilding the upstream candidate pool from raw LendingClub data
- Reconstructing the exact official paper case identities from upstream inputs alone
