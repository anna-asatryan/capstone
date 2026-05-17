# Raw Data

This folder is reserved for the raw LendingClub dataset used in the optional upstream rebuild of the project. The raw dataset is **not committed to GitHub** and should not be included in the lightweight submission zip because `loan.csv` is larger than 1GB.

The default project reproduction does **not** require the raw LendingClub file:

```bash
python run.py
```

The raw file is required only for the optional upstream rebuild:

```bash
python run.py --mode rebuild
```

## Original data source

The loan dataset was originally obtained from the LendingClub loan data hosted on Kaggle:

```text
https://www.kaggle.com/datasets/adarshsng/lending-club-loan-data-csv?resource=download
```

Because hosted datasets can change over time, the exact raw-data copy used for this project is provided separately as a zipped archive.

## Exact project copy

The exact raw-data archive used in this project is available here:

```text
https://drive.google.com/file/d/160q9keXvmJgXwaaoZrs4eyHDtAH4kgN0/view?usp=sharing 
```

Expected archive name:

```text
lendingclub_raw_data.zip
```

After downloading, place the zip file in:

```text
data/raw/lendingclub_raw_data.zip
```

Then extract it so the folder contains:

```text
data/raw/
├── README.md                   # already included in the repository
├── lendingclub_raw_data.zip    # downloaded archive, local only
├── loan.csv                    # extracted from the archive
└── LCDataDictionary.xlsx       # extracted from the archive

## Checksum verification

After downloading the zip file, you can verify that it matches the exact archive used for this project:

```bash
shasum -a 256 data/raw/lendingclub_raw_data.zip
```

Expected SHA-256:

```text
110e6ed29fd01c480a60f0b3a1edb7166305b296c3295d32fa45a7ece505a6be  data/raw/lendingclub_raw_data.zip
```

After extracting, for the individual files, you can test:

```bash
shasum -a 256 data/raw/loan.csv
shasum -a 256 data/raw/LCDataDictionary.xlsx
```

Expected SHA-256:

```text
23783ef320e4df24ac113d6e5b830edb909912b7783d49b89aacd5690dc9120c  data/raw/loan.csv
d39e281c1130c8abadce87250d97d363297e6c5c891fac6f721f076469e7a4bf  data/raw/LCDataDictionary.xlsx
```

## Required raw columns

The preprocessing code expects at least the following raw columns:

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

## Target construction

The raw `loan_status` column is converted into the binary modeling target:

```text
Charged Off -> target = 1
Fully Paid  -> target = 0
```

Rows with other loan statuses are excluded.

## Leakage removal

The preprocessing step removes post-origination and repayment-related fields before modeling, including payment totals, recoveries, last-payment fields, next-payment fields, and LendingClub internal grade/sub-grade fields.

## Feature engineering

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

## Rebuild note

To run the optional upstream rebuild, ensure that the extracted raw file exists at:

```text
data/raw/loan.csv
```

Then run from the repository root:

```bash
python run.py --mode rebuild
```

This rebuild writes only to:

```text
artifacts/build/
```

It does not modify:

```text
artifacts/frozen/
data/experiment_exports/
artifacts/tables/
artifacts/figures/
```

The official paper reproduction uses the frozen artifacts and experiment exports, not the raw dataset.