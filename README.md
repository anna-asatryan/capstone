# DS 299 Capstone — Human-AI Decision Support in Cost-Sensitive Loan Decisions

Repository: https://github.com/anna-asatryan/capstone

This repository contains the code, data contracts, frozen experiment artifacts, behavioral analysis outputs, Streamlit apps, and paper source for an AUA DS 299 capstone project on human-AI decision support. The study tests whether the timing of AI advice changes decision quality and reliance in a cost-sensitive loan decision task.

Participants completed a within-subject experiment with three protocols:

- `no_ai`: participants decided without AI advice
- `ai_first`: participants saw the AI default probability before making their final judgment
- `human_first`: participants first made an unaided judgment, then saw the AI probability, then revised or kept their judgment

The main reproduction command is:

```bash
python run.py
```

This regenerates the final behavioral tables, figures, and summary from frozen experiment artifacts and exported participant data. It does **not** require the raw LendingClub CSV, the raw-data archive, or the processed modeling CSV.

---

## 1. Main results reproduced by `python run.py`

The final behavioral analysis uses:

- 100 completed participants
- 1,800 scored trials
- three protocols: `no_ai`, `ai_first`, `human_first`

| Metric | `no_ai` | `ai_first` | `human_first` |
|---|---:|---:|---:|
| Mean trial cost | 1.2217 | 1.0117 | 0.9233 |
| Accuracy | 0.5517 | 0.6350 | 0.6500 |

Cost contrasts:

| Contrast | Difference | p-value |
|---|---:|---:|
| `no_ai` vs `ai_first` | 0.2100 | 0.017 |
| `no_ai` vs `human_first` | 0.2983 | < 0.001 |
| `ai_first` vs `human_first` | 0.0883 | 0.178 |

Additional regenerated outputs include the human-first correction matrix, weight-of-advice summary, case-level cost summary, normative deviation by difficulty, and paper-ready figures.

Interpretation boundary: AI-supported protocols reduced cost relative to no-AI. Human-first had the lowest mean cost numerically and showed clear within-trial corrections, but the direct contrast between human-first and AI-first was not statistically decisive.

---

## 2. Repository structure

```text
capstone/
├── README.md
├── requirements.txt
├── run.py
├── data/
│   ├── README.md                    # data access guide for official and optional data paths
│   ├── raw/                         # local-only raw data; large files are not committed
│   │   └── .gitkeep
│   ├── processed/                   # local-only processed modeling data
│   │   └── .gitkeep
│   └── experiment_exports/          # Supabase exports used by default reproduction
│       ├── participants.csv
│       ├── trials.csv
│       └── quiz_responses.csv
├── artifacts/
│   ├── frozen/                      # locked official experiment artifacts
│   │   ├── candidate_pool_scored.parquet
│   │   ├── final_cases.csv
│   │   ├── practice_cases.csv
│   │   ├── protocol_rotation.csv
│   │   ├── selection_manifest.json
│   │   └── cases.lock.json
│   ├── build/                       # optional upstream rebuild outputs
│   ├── tables/                      # regenerated final analysis tables
│   ├── figures/                     # regenerated final analysis figures
│   └── summary.json                 # regenerated summary of final results
├── codes/
│   ├── data_prep.py                 # preprocessing helpers for raw LendingClub data
│   ├── feature_config.py            # feature/target definitions for modeling workflow
│   ├── notebooks/                   # EDA, modeling, case design, and analysis notebooks
│   ├── pipelines/                   # official reproduction, validation, rebuild modules
│   ├── visualizations/              # auxiliary EDA/modeling diagnostic figures
│   ├── experiment_platform/         # participant-facing Streamlit + Supabase app
│   └── summary_app/                 # read-only Streamlit summary app
└── paper/                           # final paper source, bibliography, figures, and PDF
```

Large local-only files are intentionally excluded from GitHub and from the lightweight submission archive:

```text
data/raw/loan.csv
data/raw/lendingclub_raw_data.zip
data/processed/loan_v1.csv
```

---

## 3. Reproducibility commands

Run commands from the repository root.

Recommended clean setup:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python run.py --mode validate
python run.py
```

The default reproduction does **not** require:

```text
data/raw/loan.csv
data/raw/lendingclub_raw_data.zip
data/processed/loan_v1.csv
```

The optional upstream rebuild requires:

```text
data/raw/loan.csv
```

The processed modeling file is optional and notebook-facing:

```text
data/processed/loan_v1.csv
```

It is not required by `python run.py` or `python run.py --mode validate`.

This distinction is central: the official paper reproduction uses included participant exports and frozen experiment artifacts, while the optional rebuild uses the raw LendingClub dataset only for upstream provenance.

### 3.1 Official/default reproduction

```bash
python run.py
```

Equivalent explicit command:

```bash
python run.py --mode paper
```

Inputs:

```text
data/experiment_exports/
artifacts/frozen/
```

Outputs:

```text
artifacts/tables/
artifacts/figures/
artifacts/summary.json
```

This is the official one-command reproduction path for the final behavioral results. It does not require `data/raw/loan.csv`, `data/processed/loan_v1.csv`, Supabase credentials, manual notebook execution, or manual figure editing.

### 3.2 Validation

```bash
python run.py --mode validate
```

This checks frozen artifact integrity, experiment-design consistency, platform CSV synchronization, config consistency, and participant-export schema.

### 3.3 Interactive menu

```bash
python run.py --interactive
```

This opens a convenience menu for paper reproduction, summary app access, validation, and optional rebuild. It is not needed for automated reproduction.

### 3.4 Summary app

Open the deployed read-only summary app:

```bash
python run.py --mode summary --summary-target deployed
```

Launch the local read-only summary app:

```bash
python run.py --mode summary --summary-target local
```

The local summary mode first regenerates the paper outputs, then launches Streamlit from `codes/summary_app/app.py`. The deployed summary app is for presentation and exploration. The official reproduction path remains `python run.py`.

Deployed app: https://capstone-explorer.streamlit.app

### 3.5 Optional upstream rebuild

```bash
python run.py --mode rebuild
```

This mode requires:

```text
data/raw/loan.csv
```

It rebuilds upstream modeling and case-design artifacts into:

```text
artifacts/build/
```

It is provenance-only. It is not the official paper reproduction path, and it does not modify `artifacts/frozen/`, `data/experiment_exports/`, `artifacts/tables/`, or `artifacts/figures/`.

---

## 4. Data sources and data handling

Large-data access instructions are documented in:

```text
data/README.md
```

That file explains both the raw LendingClub archive and the optional processed modeling dataset, including Drive links, expected local paths, and checksums where applicable.

### 4.1 Raw LendingClub data

The upstream raw loan dataset is larger than 1GB and is not included in the GitHub repository or lightweight submission archive.

The default reproduction does **not** require the raw file:

```text
data/raw/loan.csv
```

The raw file is required only for the optional upstream rebuild:

```bash
python run.py --mode rebuild
```

Expected local path for optional rebuild:

```text
data/raw/loan.csv
```

The official/default paper reproduction uses frozen artifacts and experiment exports, not the raw LendingClub dataset.

### 4.2 Raw-to-processed preprocessing

The preprocessing logic is documented in `codes/data_prep.py` and `codes/notebooks/eda.ipynb`.

Target construction:

```text
Charged Off -> target = 1
Fully Paid  -> target = 0
```

Rows with other `loan_status` values are excluded.

Main leakage-removal rule: post-origination repayment, recovery, collection, and payment-history columns are removed before modeling. LendingClub internal `grade` and `sub_grade` are also excluded.

Final model features:

```text
loan_amnt
term
int_rate
dti
revol_util
home_ownership
purpose
log_annual_inc
credit_history_years
```

Derived variables:

```text
log_annual_inc = log1p(annual_inc)
credit_history_years = issue_d - earliest_cr_line, in years
```

### 4.3 Processed modeling data

```text
data/processed/loan_v1.csv
```

This file is used by the upstream modeling and case-design notebooks. It is not committed to GitHub and should not be included in the lightweight submission archive because it is approximately 200 MB.

The official default reproduction does not require it, because final behavioral results use frozen experiment artifacts and exported participant data:

```text
data/experiment_exports/
artifacts/frozen/
```

If needed for upstream notebook inspection, the exact processed-data copy is documented in:

```text
data/README.md
```

### 4.4 Experiment exports

```text
data/experiment_exports/
├── participants.csv
├── trials.csv
└── quiz_responses.csv
```

These are Supabase exports collected from the deployed experiment platform. They are fixed inputs for the final behavioral analysis and are required by the official default reproduction.

### 4.5 Frozen experiment artifacts

```text
artifacts/frozen/
├── candidate_pool_scored.parquet
├── final_cases.csv
├── practice_cases.csv
├── protocol_rotation.csv
├── selection_manifest.json
└── cases.lock.json
```

These files define the official experiment boundary. They should be treated as locked after data collection. Validation checks the frozen files and verifies that the participant-facing platform copy matches them.

---

## 5. Pipeline modules

The pipeline code is in `codes/pipelines/`:

| File | Purpose |
|---|---|
| `common.py` | Shared paths, constants, cost logic, loading helpers, hash utilities, and reusable table/figure helpers |
| `reproduce_paper.py` | Official paper reproduction from `data/experiment_exports/` and `artifacts/frozen/` |
| `validate_artifacts.py` | Frozen artifact existence, required columns, counts, and manifest/hash consistency |
| `validate_experiment_design.py` | Design structure, block/protocol rotation, platform CSV sync, config consistency, and export schema |
| `rebuild_from_upstream.py` | Optional rebuild from `data/raw/loan.csv` into `artifacts/build/` |

The default command regenerates both final tables and final figures.

---

## 6. Generated outputs

Default reproduction writes compact tables to:

```text
artifacts/tables/
```

Current final tables:

```text
protocol_outcomes.csv
protocol_contrasts.csv
human_first_correction_matrix.csv
woa_summary.csv
case_level_cost.csv
```

Default reproduction writes figures to:

```text
artifacts/figures/
```

Current final figures:

```text
cost_accuracy_by_protocol.png
human_first_correction_matrix.png
woa_distribution.png
case_risk_cost_scatter.png
normative_deviation_by_difficulty.png
```

For the final paper, use the generated figure files from `artifacts/figures/`. Do not manually edit the generated figures outside the code pipeline.

The paper source uses selected figures copied into:

```text
paper/figures/
```

These are copies of generated files from `artifacts/figures/` for LaTeX compilation. The generated source-of-truth figures remain in `artifacts/figures/` and are recreated by:

```bash
python run.py
```

---

## 7. Notebooks

The notebooks document the research workflow:

| Notebook | Role |
|---|---|
| `codes/notebooks/eda.ipynb` | Cleans raw LendingClub data, checks features, constructs processed modeling dataset, and documents train-only difficulty variables |
| `codes/notebooks/modeling.ipynb` | Fits/calibrates candidate models, selects logistic regression, and exports the scored candidate pool/coefficient artifacts |
| `codes/notebooks/case_design.ipynb` | Audits the locked case design and explains the selection logic; frozen artifacts are the source of truth after data collection |
| `codes/notebooks/analysis.ipynb` | Computes final behavioral outcomes, paired tests, process metrics, compact tables, and final diagnostic figures |

The notebooks are explanatory and auditable. The official one-command behavioral reproduction is `python run.py`.

---

## 8. Streamlit apps

### 8.1 Participant-facing experiment platform

```bash
cd codes/experiment_platform
streamlit run app.py
```

This app requires Supabase credentials in a local Streamlit secrets file. Do not commit real credentials.

### 8.2 Read-only summary app

Preferred local launch:

```bash
python run.py --mode summary --summary-target local
```

Alternative direct launch:

```bash
streamlit run codes/summary_app/app.py
```

The summary app is for presentation and exploration. It is not required for default reproduction.

---

## 9. Environment setup

Use Python 3.11. The repository was successfully tested in a clean virtual environment with Python 3.11.1.

Python 3.13 is not recommended for this project because some pinned scientific dependencies may try to build from source instead of installing prebuilt wheels.

### macOS/Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python run.py --mode validate
python run.py
```

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python run.py --mode validate
python run.py
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\\.venv\\Scripts\\Activate.ps1
```

### Windows Command Prompt

```cmd
py -3.11 -m venv .venv
.venv\\Scripts\\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python run.py --mode validate
python run.py
```

---

## 10. Reproducibility statement

The repository separates the locked behavioral reproduction path from the optional upstream raw-data rebuild. The default command regenerates the final reported behavioral results from included participant exports and frozen artifacts. The raw LendingClub file and processed modeling dataset are documented but excluded because of size constraints; they are not needed for the official paper reproduction. This structure supports reproducibility while avoiding oversized raw-data commits and private credential leakage.

The project repository is available at: https://github.com/anna-asatryan/capstone