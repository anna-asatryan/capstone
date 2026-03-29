# Interaction Structure in AI-Assisted Decision Support Systems

**Author:** Anna Asatryan  
**Supervisor:** Karen Hovhannisyan  
**Institution:** American University of Armenia, Akian College of Science & Engineering  
**Course:** DS 299 Capstone, Spring 2026  

---

## Project Overview

This project investigates how the timing of AI advice affects decision-making in human–AI decision support systems (DSS). The central research question is whether presenting AI predictions before or after human judgment changes reliance behavior, confidence calibration, and decision accuracy.

The experimental setting is a credit risk decision task using real LendingClub data. Participants act as loan officers and make approval decisions under asymmetric misclassification costs.

The key contribution of this project is the explicit separation between:

- **Model-level performance** (offline predictive metrics such as AUC, Brier score, calibration)
- **System-level performance** (realized outcomes when humans interact with model outputs)

Interaction structure is treated as a **post-model evaluation layer**, allowing the study to isolate how different protocols affect decision outcomes while holding the predictive model fixed.

---

## Components

### 1. Predictive Model
- Logistic Regression with calibrated probabilities (isotonic calibration)
- Trained on LendingClub loan data with temporal split (pre/post 2016)
- Selected based on **calibration quality (Brier score, ECE)** rather than marginal AUC improvements
- Model is **frozen before experimentation**

**Decision-Theoretic Context:**
- Decisions are evaluated under asymmetric costs (false approvals vs false rejections)
- Model outputs calibrated probabilities
- Optimal decision rule is theoretically cost-sensitive (not fixed at 0.5 threshold)

---

### 2. Case Design

- 18 experimental cases
- Stratified across:
  - **Difficulty** (easy / medium / hard)
  - **Model correctness** (correct / incorrect)

- Balanced design:
  - 6 cells (3 difficulty × 2 correctness)
  - 3 cases per cell

**Additional constraints (critical):**
- Cases span a **range of predicted probabilities (confidence levels)**
- Include **model–optimal disagreement cases**
- Ensure **feature diversity across cases**

**Important design principle:**
- Difficulty is **model-independent**, computed from base rates in feature bins
- Prevents circularity between model predictions and task difficulty

---

### 3. Behavioral Experiment

- **Within-subject design**
- 18 trials per participant
- Interaction protocols:
  - AI-first (AI shown before human decision)
  - Human-first (AI shown after initial human decision)
  - No-AI (baseline)

- Protocol order is **counterbalanced across participants**

**Per trial, participants provide:**
- Binary decision (approve / reject)
- Confidence rating (required)

**System logging includes:**
- Initial decision (human-first only)
- Final decision
- Decision revision (change vs no change)
- Confidence rating
- Decision time

---

## Evaluation Framework

### Model-Level Evaluation (offline)
- AUC (discrimination)
- Brier Score (calibration + accuracy)
- Log Loss
- Expected Calibration Error (ECE)

### System-Level Evaluation (experimental)
- Decision accuracy (final decisions)
- Confidence calibration (confidence vs correctness)
- Reliance behavior:
  - agreement rate with model
  - override behavior (when human disagrees)
- **Model–system performance gap**:
  - difference between standalone model accuracy and realized human–AI performance



---

## Repository Structure

```text

capstone/
├── outputs/
│   ├── case_design.pdf             # Exported summary of case selection
│   ├── modeling.pdf                # Model results (metrics, calibration)
│   └── eda.pdf                     # EDA summary (features, difficulty)
│
├── artifacts/
│   ├── protocol_rotation.csv       # Counterbalancing scheme
│   ├── final_cases.csv             # Final 18 experimental cases
│   └── test_predictions.parquet    # Frozen model predictions
│
├── data/
│   ├── raw/
│   │   ├── loan.csv                # Raw dataset (not versioned)
│   │   └── LCDataDictionary.xlsx   # Feature descriptions
│   │
│   └── processed/
│       └── loan_v1.csv             # Cleaned dataset (EDA output)
│
├── paper/
│   └── CapstonePaperDraft.pdf      # IEEE-style paper draft
│
├── codes/
│   ├── notebooks/
│   │   ├── eda.ipynb               # Data cleaning + feature engineering
│   │   ├── modeling.ipynb          # Training + calibration + evaluation
│   │   └── case_design.ipynb       # Case selection logic
│   │
│   ├── feature_config.py           # Feature definitions (NUM_COLS, CAT_COLS)
│   ├── data_prep.py                # Data loading + preprocessing
│   ├── __init__.py     
│   │
│   └── visualizations/
│       ├── difficulty_interactions.png
│       ├── normative_agreement.png
│       ├── feature_shift.png
│       ├── confusion_matrices.png
│       ├── prob_distribution.png
│       └── calibration_curves.png
│
├── models/
│
├── README.md                       # Project documentation
├── requirements.txt                # Dependencies
└── venv/                           # Local environment 
```

---

## Setup

### Requirements

- Python 3.9+
- See `requirements.txt` for package versions

### Installation
```bash
git clone <repository-url>
cd capstone
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## Data Setup

The raw dataset (1.19 GB) is not tracked in this repository.

**Download:** [LendingClub Loan Data on Kaggle](https://www.kaggle.com/datasets/adarshsng/lending-club-loan-data-csv)  
**File needed:** `accepted_2007_to_2018Q4.csv`  
**Rename to:** `loan.csv`  
**Place at:** `data/raw/loan.csv`

No other manual data setup is required. All processed files are generated 
by the notebooks.

---
## Reproducing Results

Run notebooks in the following order:

### 1. EDA (`codes/notebooks/eda.ipynb`)
- Loads raw data via `data_prep.py`
- Cleans dataset and constructs features
- Computes model-independent difficulty tiers

**Exports:**
- `data/processed/loan_v1.csv`

---

### 2. Modeling (`codes/notebooks/modeling.ipynb`)
- Loads processed dataset
- Trains Logistic, XGBoost, HistGradientBoosting
- Applies probability calibration
- Selects final model based on Brier score

**Exports:**
- `artifacts/test_predictions.parquet`

---

### 3. Case Design (`codes/notebooks/case_design.ipynb`)
- Loads frozen predictions
- Stratifies cases by:
  - difficulty × correctness
  - ensures confidence spread

**Outputs:**
- `artifacts/final_cases.csv`

---

## Experiment Status

- Web-based DSS: in development  
- Target participants: 100  
- Data collection: pending  

---

## Paper

Draft available at:
- `paper/CapstonePaperDraft.pdf`
