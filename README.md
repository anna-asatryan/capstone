# DS 299 Capstone — Human-AI Decision Support in Loan Default Prediction

Within-subject behavioral experiment studying how AI decision support affects human judgment across three protocol conditions (no AI, human-first, AI-first). Participants evaluate 18 LendingClub loan cases selected to span calibrated difficulty tiers.

## Repo structure

```
codes/
  notebooks/            # EDA → modeling → case design pipeline
  experiment_platform/  # Streamlit participant app (→ capstone-experiment-platform)
  summary_app/          # Dash results dashboard (→ capstone-analysis-app, post-study)
  pipelines/            # Reproduction CLI backends
  data_prep.py          # Feature engineering
  feature_config.py     # Feature/target definitions
artifacts/
  frozen/               # Locked canonical artifacts (SHA256-verified, never regenerated)
data/
  raw/                  # LendingClub source CSV (gitignored, ~1 GB)
  processed/            # Cleaned feature set
paper/                  # Quarto manuscript
docs/                   # Architecture and reproduction guides
```

## Quick start

Run the entrypoint script without arguments for an interactive menu, or pass a mode directly:

```bash
python run.py                        # interactive menu (defaults to paper reproduction)
python run.py --mode summary         # launch summary visualisation app
python run.py --mode validate        # check integrity of all frozen artifacts
python run.py --mode rebuild-design  # best-effort upstream design rebuild (audit only)
```

## Notebook pipeline

```
codes/notebooks/eda.ipynb
  → data/processed/loan_v1.csv (cleaned features, difficulty tiers, case_id)

codes/notebooks/modeling.ipynb
  → artifacts/test_predictions.parquet (scored test set)

codes/notebooks/case_design.ipynb
  → artifacts/frozen/ (18 final cases, 2 practice cases, protocol rotation)
```

Re-running notebooks regenerates working copies in `artifacts/`. The frozen boundary in `artifacts/frozen/` is SHA256-locked and never overwritten.

## Frozen artifact boundary

```
artifacts/frozen/
  final_cases.csv               18 experimental cases
  practice_cases.csv            2 warm-up cases
  protocol_rotation.csv         block order per condition
  candidate_pool_scored.parquet full scored pool used for selection
  cases.lock.json               SHA256 hashes + locking git commit
  selection_manifest.json       selection parameters and thresholds
```

Validation fails loudly if any hash mismatches. Run `python run.py --mode validate` to check.

## Standalone repos

| Standalone repo | Source in this repo | Sync trigger |
|---|---|---|
| `capstone-experiment-platform` | `codes/experiment_platform/` | push to `main` |
| `capstone-analysis-app` | `codes/summary_app/` | push to `main` after study |

Synced automatically via GitHub Actions (`.github/workflows/`).

## Experiment platform

Run locally:

```bash
cd codes/experiment_platform
streamlit run app.py
```

Requires a Supabase project. Copy `.streamlit/secrets.toml.template` → `.streamlit/secrets.toml` and fill in credentials.

## Full documentation

- [docs/REPRODUCTION.md](docs/REPRODUCTION.md) — modes, commands, frozen boundary details
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — pipeline components and data contracts
