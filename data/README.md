# Data Directory Guide

This directory documents the data inputs used in the DS 299 capstone repository.

The project separates the **official paper-reproduction path** from the **optional upstream modeling workflow**. The official path is intentionally lightweight and does not require the large LendingClub raw or processed modeling files.

---

## 1. Official default reproduction

This is the path used to reproduce the final behavioral-analysis results reported in the paper.

Run from the repository root:

```bash
python run.py --mode validate
python run.py
```

This path uses:

```text
data/experiment_exports/
artifacts/frozen/
```

The official/default reproduction does **not** require:

```text
data/raw/loan.csv
data/raw/lendingclub_raw_data.zip
data/processed/loan_v1.csv
```

The default reproduction regenerates:

```text
artifacts/tables/
artifacts/figures/
artifacts/summary.json
```

---

## 2. Folder structure

```text
data/
├── README.md
├── experiment_exports/
│   ├── participants.csv
│   ├── trials.csv
│   └── quiz_responses.csv
├── processed/
│   └── loan_v1.csv              # optional local file; not committed
└── raw/
    ├── loan.csv                 # optional local file; not committed
    ├── LCDataDictionary.xlsx    # optional local file
    └── lendingclub_raw_data.zip # optional local archive; not committed
```

For the lightweight GitHub/submission package, only `data/README.md` and `data/experiment_exports/` are required for the official reproduction path.

---

## 3. Experiment exports

Folder:

```text
data/experiment_exports/
```

Files:

```text
participants.csv
trials.csv
quiz_responses.csv
```

These files are included in the repository and are used by the official default reproduction. They are exported from the Supabase backend after data collection.

---

## 4. Raw LendingClub data

The raw LendingClub dataset is larger than 1GB and is not committed to GitHub or included in the lightweight submission zip.

Original source: https://www.kaggle.com/datasets/adarshsng/lending-club-loan-data-csv?resource=download

Exact raw-data archive used for this project: https://drive.google.com/file/d/160q9keXvmJgXwaaoZrs4eyHDtAH4kgN0/view?usp=sharing 

Expected archive filename:

```text
lendingclub_raw_data.zip
```

Expected local paths after download and extraction:

```text
data/raw/lendingclub_raw_data.zip
data/raw/loan.csv
data/raw/LCDataDictionary.xlsx
```

This raw data is needed only for the optional upstream rebuild:

```bash
python run.py --mode rebuild
```

The official/default paper reproduction uses `data/experiment_exports/` and `artifacts/frozen/` instead.

---

## 5. Processed modeling data

The processed modeling dataset is optional and notebook-facing only. It is not required for the official paper reproduction.

Expected local path:

```text
data/processed/loan_v1.csv
```

Exact processed-data copy: https://drive.google.com/file/d/1-pObaAedLyYoYVCSmduq5RsHuEUbx1SE/view?usp=sharing 

This file is used by the notebook workflow, especially the EDA/modeling/case-design sequence. The scripted official reproduction does not read this file.

Default reproduction still works without it:

```bash
python run.py --mode validate
python run.py
```

---

## 6. Optional upstream rebuild

The optional upstream rebuild requires the raw LendingClub file:

```text
data/raw/loan.csv
```

Run from the repository root:

```bash
python run.py --mode rebuild
```

This mode writes rebuilt upstream artifacts only to:

```text
artifacts/build/
```

It does **not** modify:

```text
artifacts/frozen/
data/experiment_exports/
artifacts/tables/
artifacts/figures/
artifacts/summary.json
```

The official paper analysis uses the locked files in `artifacts/frozen/` and the participant exports in `data/experiment_exports/`, not the optional rebuild outputs.

---

## 7. Required raw columns

The preprocessing code expects at least the following raw LendingClub columns:

```text
loan_status
issue_d
earliest_cr_line
annual_inc
dti
loan_amnt
term
int_rate
revol_util
home_ownership
purpose
```

---

## 8. Target construction

The raw `loan_status` field is converted into the binary modeling target:

```text
Charged Off -> target = 1
Fully Paid  -> target = 0
```

Rows with other loan statuses are excluded.

---

## 9. Leakage removal and feature engineering

The preprocessing step removes post-origination and repayment-related fields before modeling, including payment totals, recoveries, last-payment fields, next-payment fields, and LendingClub internal grade/sub-grade fields.

The final modeling feature set is:

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
credit_history_years = issue_d - earliest_cr_line, measured in years
```
