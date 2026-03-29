import pandas as pd
import numpy as np

REQUIRED_COLS = [
    'loan_status', 'issue_d', 'earliest_cr_line',
    'annual_inc', 'dti'
]

def load_and_clean(path):
    df = pd.read_csv(path, low_memory=False)

    # ---------------------------
    # SCHEMA VALIDATION
    # ---------------------------
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    # ---------------------------
    # TARGET
    # ---------------------------
    df['loan_status'] = df['loan_status'].astype(str).str.strip()
    df = df[df['loan_status'].isin(["Fully Paid", "Charged Off"])].copy()
    df['target'] = (df['loan_status'] == "Charged Off").astype(int)

    # ---------------------------
    # LEAKAGE REMOVAL
    # ---------------------------
    leakage_cols = [
        "out_prncp","out_prncp_inv","total_pymnt","total_pymnt_inv",
        "total_rec_prncp","total_rec_int","total_rec_late_fee",
        "recoveries","collection_recovery_fee",
        "last_pymnt_d","last_pymnt_amnt",
        "next_pymnt_d","last_credit_pull_d"
    ]
    df = df.drop(columns=leakage_cols, errors="ignore")

    # remove LC internal grading (leakage proxy)
    df = df.drop(columns=["grade","sub_grade"], errors="ignore")

    # ---------------------------
    # DATES
    # ---------------------------
    df['issue_d'] = pd.to_datetime(df['issue_d'], format='%b-%Y', errors='coerce')
    df['earliest_cr_line'] = pd.to_datetime(df['earliest_cr_line'], format='%b-%Y', errors='coerce')

    # ---------------------------
    # TYPE CLEANING
    # ---------------------------
    if 'int_rate' in df.columns:
        df['int_rate'] = (
            df['int_rate']
            .astype(str)
            .str.replace('%', '', regex=False)
        )
        df['int_rate'] = pd.to_numeric(df['int_rate'], errors='coerce')

    if 'term' in df.columns:
        df['term'] = df['term'].astype(str).str.strip()
        df['term'] = df['term'].astype('category')

    if 'revol_util' in df.columns:
        df['revol_util'] = (
            df['revol_util']
            .astype(str)
            .str.replace('%', '', regex=False)
        )
        df['revol_util'] = pd.to_numeric(df['revol_util'], errors='coerce')

    # ---------------------------
    # PURPOSE FILTER 
    # ---------------------------
    if 'purpose' in df.columns:
        purpose_counts = df['purpose'].value_counts(normalize=True)
        valid_purposes = purpose_counts[purpose_counts >= 0.005].index

        df = df[df['purpose'].isin(valid_purposes)].copy()

        df['purpose'] = df['purpose'].astype('category')

    return df



def build_features(df):
    df = df.copy()

    # ---------------------------
    # FEATURE ENGINEERING
    # ---------------------------
    df['credit_history_years'] = (
        (df['issue_d'] - df['earliest_cr_line']).dt.days / 365.25
    ).clip(lower=0)

    df['log_annual_inc'] = np.log1p(df['annual_inc'].clip(lower=0))

    # ---------------------------
    # FEATURE VALIDATION
    # ---------------------------
    assert df['credit_history_years'].notna().mean() > 0.95, \
        "Too many missing values in credit_history_years"

    assert df['log_annual_inc'].notna().mean() > 0.95, \
        "Too many missing values in log_annual_inc"

    # sanity checks (optional but recommended)
    assert (df['credit_history_years'] >= 0).all(), \
        "Negative credit history detected"

    return df