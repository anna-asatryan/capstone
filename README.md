# DS 299 Capstone — Human-AI Decision Support in Cost-Sensitive Loan Decisions

This repository contains the code, frozen experiment artifacts, exported behavioral data, generated analysis outputs, Streamlit apps, and paper source for an AUA DS 299 capstone project on human-AI decision support. The study tests whether the timing of AI advice changes decision quality and reliance in a cost-sensitive loan decision task.

## Important links and entry points

| Item | Link |
|---|---|
| GitHub repository | https://github.com/anna-asatryan/capstone |
| Deployed summary app | https://capstone-explorer.streamlit.app |
| Deployed experiment platform | https://capstone-study.streamlit.app|

Participants completed a within-subject experiment with three protocols:

- `no_ai`: participants decided without AI advice
- `ai_first`: participants saw the AI default probability before making their final judgment
- `human_first`: participants first made an unaided judgment, then saw the AI probability, then revised or kept their judgment

---

## 1. Quick start: environment and reproduction

Use **Python 3.11**. The project was tested with Python 3.11 on macOS and Windows. Python 3.13 is not recommended because some pinned scientific dependencies may not install reliably.

The official one-command reproduction is:

```bash
python run.py
```

This regenerates the final behavioral tables, figures, and summary from included frozen experiment artifacts and exported participant data. It does **not** require the raw LendingClub CSV, processed modeling CSV, Supabase credentials, Streamlit apps, manual notebook execution, or manual figure editing.


## Getting the project

You can work from either the GitHub repository or the submitted ZIP archive.

### Option A: GitHub repository

Clone the repository and enter the project root:

```bash
git clone https://github.com/anna-asatryan/capstone.git
cd capstone
```

### Option B: Submitted ZIP archive

Unzip the submitted archive, then enter the extracted project folder:

```
cd Anna_Asatryan_DS299
```

### macOS / Linux

Run from the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

python run.py --mode validate
python run.py
```

### Windows PowerShell

Run from the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

python run.py --mode validate
python run.py
```

If PowerShell blocks activation, run this once in the same PowerShell window:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

If `py -3.11` is not recognized, install Python 3.11 from python.org and include the Python Launcher during installation, or use the full path to the Python 3.11 executable.

### Windows Command Prompt

Run from the repository root:

```cmd
py -3.11 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

python run.py --mode validate
python run.py
```

### Interactive menu

After installing dependencies, you can also use the guided menu:

```bash
python run.py --interactive
```

The interactive menu exposes paper reproduction, summary app access, validation, and optional upstream rebuild. For automated grading/reproduction, use the non-interactive official command:

```bash
python run.py
```

---

## 2. Required software and dependencies

Required for the official default reproduction:

- Python 3.11
- `pip`
- Python packages listed in `requirements.txt`

Optional:

- TeX Live 2024+ or another LaTeX distribution, only if rebuilding the PDF from `paper/main.tex`
- Streamlit, installed through `requirements.txt`, only if launching the summary app or participant-facing experiment platform
- Supabase project credentials, only if running the participant-facing experiment platform with database writes
- Raw LendingClub data, only if running the optional upstream rebuild

No R environment is required.

---

## 3. Project objective and main reproduced results

The objective is to evaluate whether AI advice timing changes realized decision quality in a cost-sensitive human-AI decision-support task. The final behavioral analysis uses:

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

These values are regenerated in `artifacts/summary.json` and `artifacts/tables/` by `python run.py`.

Interpretation boundary: AI-supported protocols reduced cost relative to no-AI. Human-first had the lowest mean cost numerically and showed clear within-trial corrections, but the direct contrast between human-first and AI-first was not statistically decisive.

---

## 4. Repository structure

```text
capstone/
├── README.md
├── requirements.txt
├── run.py                         # main CLI entrypoint for reproduction, validation, summary app, and rebuild modes
├── data/
│   ├── README.md                  # data access guide for official and optional data paths
│   ├── raw/                       # local-only raw data; large files are not committed
│   │   └── .gitkeep
│   ├── processed/                 # local-only processed modeling data
│   │   └── .gitkeep
│   └── experiment_exports/        # Supabase exports used by default reproduction
│       ├── participants.csv
│       ├── trials.csv
│       └── quiz_responses.csv
├── artifacts/
│   ├── frozen/                    # locked official experiment artifacts
│   ├── build/                     # optional upstream rebuild outputs
│   ├── tables/                    # regenerated final analysis tables
│   ├── figures/                   # regenerated final analysis figures
│   └── summary.json               # regenerated summary of final results
├── codes/
│   ├── data_prep.py               # preprocessing helpers for raw LendingClub data
│   ├── feature_config.py          # feature/target definitions for modeling workflow
│   ├── notebooks/                 # EDA, modeling, case design, and analysis notebooks
│   ├── pipelines/                 # official reproduction, validation, rebuild modules
│   ├── visualizations/            # auxiliary EDA/modeling diagnostic figures
│   ├── experiment_platform/       # participant-facing Streamlit + Supabase app
│   └── summary_app/               # read-only Streamlit summary app
└── paper/                         # final paper source, bibliography, figures, and PDF
```

Large local-only files are intentionally excluded from GitHub and from the lightweight submission archive:

```text
data/raw/loan.csv
data/raw/lendingclub_raw_data.zip
data/processed/loan_v1.csv
```

---

## 5. Data sources and data handling

The official reproduction uses included files only:

```text
data/experiment_exports/
artifacts/frozen/
```

Large-data access instructions are documented in:

```text
data/README.md
```

That file includes the original Kaggle source, Google Drive links for the optional raw and processed data, and expected local paths.

### 5.1 Experiment exports

```text
data/experiment_exports/
├── participants.csv
├── trials.csv
└── quiz_responses.csv
```

These are Supabase exports collected from the deployed experiment platform. They are fixed inputs for the final behavioral analysis and are required by the official default reproduction.

### 5.2 Frozen experiment artifacts

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

### 5.3 Raw LendingClub data

The upstream raw loan dataset is larger than 1GB and is not included in the GitHub repository or lightweight submission archive.

Original source: https://www.kaggle.com/datasets/adarshsng/lending-club-loan-data-csv?resource=download

Expected local path for optional rebuild:

```text
data/raw/loan.csv
```

The raw file is required only for:

```bash
python run.py --mode rebuild
```

It is not required for `python run.py`.

### 5.4 Raw-to-processed preprocessing

The preprocessing logic is documented in `codes/data_prep.py` and `codes/notebooks/eda.ipynb`.

Target construction:

```text
Charged Off -> target = 1
Fully Paid  -> target = 0
```

Rows with other `loan_status` values are excluded. Post-origination repayment, recovery, collection, and payment-history columns are removed before modeling. LendingClub internal `grade` and `sub_grade` are also excluded.

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

### 5.5 Processed modeling data

```text
data/processed/loan_v1.csv
```

This file is used by the upstream notebook workflow. It is not committed to GitHub and should not be included in the lightweight submission archive because it is approximately 200 MB. It is optional and not required for `python run.py`.

---

## 6. How to run the code

Run commands from the repository root.

| Task | Command |
|---|---|
| Official paper reproduction | `python run.py` |
| Explicit paper mode | `python run.py --mode paper` |
| Validate artifacts/design/exports | `python run.py --mode validate` |
| Guided menu | `python run.py --interactive` |
| Deployed summary app | `python run.py --mode summary --summary-target deployed` |
| Local summary app | `python run.py --mode summary --summary-target local` |
| Optional upstream rebuild | `python run.py --mode rebuild` |

### Optional upstream rebuild

Rebuild mode requires:

```text
data/raw/loan.csv
```

It writes rebuilt upstream artifacts to:

```text
artifacts/build/
```

It is provenance-only. It is not the official paper reproduction path, and it does not modify:

```text
artifacts/frozen/
data/experiment_exports/
artifacts/tables/
artifacts/figures/
artifacts/summary.json
```

If `data/raw/loan.csv` is missing, rebuild mode exits with a clear message explaining where to place the raw file.

---

## 7. How figures and tables in the paper are generated

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

The paper uses selected figures copied into:

```text
paper/figures/
```

These are copies of generated files from `artifacts/figures/` for LaTeX compilation. The generated source-of-truth figures remain in `artifacts/figures/` and are recreated by:

```bash
python run.py
```

Do not manually edit the generated figures outside the code pipeline.

---

## 8. Rebuilding the paper PDF

The submitted PDF is included at:

```text
paper/Anna_Asatryan_DS299_Capstone_Paper.pdf
```

To rebuild it from LaTeX source:

```bash
cd paper
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
cp main.pdf Anna_Asatryan_DS299_Capstone_Paper.pdf
```

The paper figures are copied from `artifacts/figures/` into `paper/figures/` for LaTeX compilation.

---

## 9. Pipeline modules

The pipeline code is in `codes/pipelines/`:

| File | Purpose |
|---|---|
| `common.py` | Shared paths, constants, cost logic, loading helpers, hash utilities, and reusable table/figure helpers |
| `reproduce_paper.py` | Official paper reproduction from `data/experiment_exports/` and `artifacts/frozen/` |
| `validate_artifacts.py` | Frozen artifact existence, required columns, counts, and manifest/hash consistency |
| `validate_experiment_design.py` | Design structure, block/protocol rotation, platform CSV sync, config consistency, and export schema |
| `rebuild_from_upstream.py` | Optional rebuild from `data/raw/loan.csv` into `artifacts/build/` |

---

## 10. Notebooks

The notebooks document the research workflow:

| Notebook | Role |
|---|---|
| `codes/notebooks/eda.ipynb` | Cleans raw LendingClub data, checks features, constructs processed modeling dataset, and documents train-only difficulty variables |
| `codes/notebooks/modeling.ipynb` | Fits/calibrates candidate models, selects logistic regression, and exports the scored candidate pool/coefficient artifacts |
| `codes/notebooks/case_design.ipynb` | Audits the locked case design and explains the selection logic; frozen artifacts are the source of truth after data collection |
| `codes/notebooks/analysis.ipynb` | Computes final behavioral outcomes, paired tests, process metrics, compact tables, and final diagnostic figures |

The notebooks are explanatory and auditable. The official one-command behavioral reproduction is:

```bash
python run.py
```

---

## 11. Streamlit apps

### 11.1 Participant-facing experiment platform

From the repository root:

```bash
streamlit run codes/experiment_platform/app.py
```

Or from inside the platform folder:

```bash
cd codes/experiment_platform
streamlit run app.py
```

This app requires Supabase credentials in a local Streamlit secrets file. Do not commit real credentials.

### 11.2 Read-only summary app

Preferred local launch:

```bash
python run.py --mode summary --summary-target local
```

Alternative direct launch:

```bash
streamlit run codes/summary_app/app.py
```

The deployed summary app is available at: https://capstone-explorer.streamlit.app

The summary app is for presentation and exploration. It is not required for default reproduction.

---

## 12. Reproducibility statement

The repository separates the locked behavioral reproduction path from the optional upstream raw-data rebuild. The default command regenerates the final reported behavioral results from included participant exports and frozen artifacts. The raw LendingClub file and processed modeling dataset are documented but excluded because of size constraints; they are not needed for the official paper reproduction. This structure supports reproducibility while avoiding oversized raw-data commits and private credential leakage.

The project repository is available at: https://github.com/anna-asatryan/capstone