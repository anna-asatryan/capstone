# Reproduction Guide

## Commands

```bash
# Interactive menu (defaults to paper reproduction)
python run.py

# Launch the summary app against most recent pipeline outputs
python run.py --mode summary

# Validate frozen artifact hashes and schemas
python run.py --mode validate

# Best-effort rebuild upstream design (audit only)
python run.py --mode rebuild-design

# Run the experiment platform locally
cd codes/experiment_platform && streamlit run app.py
```

## What each mode does

### Paper mode (default)

Official deterministic reproduction path.

1. Validates `artifacts/frozen/` against `cases.lock.json`
2. Loads the frozen scored candidate pool and selected cases
3. Loads participant exports from `artifacts/frozen/experiment_exports/`
4. Regenerates downstream analysis tables and figures in `artifacts/analysis/latest/`

### Summary mode

Launches the Dash summary app against the most recent pipeline outputs. If the analysis bundle is not found, it runs the `paper` mode first.

### Validate mode

Validates:
1. Frozen artifact integrity (hashes + required columns)
2. Experiment design structure + platform CSV sync
3. Participant export schema (if present)

### Rebuild-design mode

Best-effort re-run from upstream inputs to generate the experiment design.

1. Reads `data/raw/loan.csv`
2. Rebuilds cleaned features and model-independent difficulty tiers
3. Retrains the scripted logistic + calibration pipeline
4. Reconstructs a scored candidate pool and selects cases using extracted notebook heuristics
5. Compares rebuilt case identities against the official frozen set
6. Outputs go to `artifacts/build/` only

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
  experiment_exports/
```

If any locked file is missing or its hash changes, validation fails loudly.

## Output locations

Downstream pipeline outputs (generated on each run, gitignored):

```
artifacts/analysis/latest/summary.json
artifacts/analysis/latest/tables/*.csv
artifacts/analysis/latest/figures/*.png
```

Best-effort rebuild intermediates (generated on rebuild, gitignored):

```
artifacts/build/
```

## Deterministic vs best-effort

Truly deterministic:
- Frozen artifact validation
- Downstream summaries computed from the frozen participant exports and case set
- Summary app rendering from generated analysis tables

Best-effort only:
- Rebuilding the upstream candidate pool from raw LendingClub data
- Reconstructing the exact official paper case identities from upstream inputs alone
