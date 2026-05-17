# Summary App — Human-AI Decision Explorer

This folder contains the Streamlit summary app used as an interactive companion to the capstone poster and final paper.
It is a **read-only analysis app**: it loads already-exported study data and lets a reviewer inspect the main behavioral results in more detail. 

## Purpose

The app complements the static poster by exposing the underlying evidence behind the main findings:

- protocol-level decision cost and accuracy;
- human-first revision behavior;
- weight-of-advice (WOA) and reliance patterns;
- case-level behavior across the 18 locked loan cases;
- an optional safe demo link to the participant-facing experiment platform.

## Main pages

- **Overview** — high-level study summary, workflow explanation, key findings, and demo button.
- **Protocol Comparator** — protocol-level outcome comparisons (cost, accuracy, Brier score, approval rate, paired contrasts, and selected sensitivity checks).
- **Human-First Revision** — pre/post revision behavior in the human-first condition, including correction counts and revision paths.
- **Reliance Explorer** — WOA distribution and threshold-implied action alignment.
- **Case Explorer** — case-level risk/cost view and where AI support helped or hurt case-by-case.

## Folder structure

```text
summary_app/
├── app.py                    # Streamlit entrypoint
├── charts.py                 # Plotly chart builders
├── components.py             # reusable UI helpers and CSS loader
├── data_loader.py            # bundled-data / repo-artifact loading logic
├── metrics.py                # analysis helpers used by the app
├── README.md                 # this file
├── requirements.txt          # app dependencies
├── .streamlit/
│   └── config.toml           # Streamlit UI configuration
├── assets/
│   ├── styles.css            # custom app styling
│   └── hai1.png              # overview workflow background image
└── data/
    ├── participants.csv      # bundled participant export
    ├── trials.csv            # bundled trial-level export
    ├── quiz_responses.csv    # bundled onboarding quiz export
    ├── final_cases.csv       # locked 18 scored cases
    ├── practice_cases.csv    # locked 2 practice cases
    └── protocol_rotation.csv # locked protocol rotation
```

## Data loading behavior

The app first tries to load the bundled CSV files inside `summary_app/data/`.
This keeps the app portable and allows standalone deployment.

If bundled files are absent, the app falls back to the repository-level artifacts when available, including:

- `data/experiment_exports/participants.csv`
- `data/experiment_exports/trials.csv`
- `data/experiment_exports/quiz_responses.csv`
- `artifacts/frozen/final_cases.csv`
- `artifacts/frozen/practice_cases.csv`
- `artifacts/frozen/protocol_rotation.csv`

This means the same code can run either:

1. as a standalone deployed summary app with bundled data; or
2. from the main capstone repository using exported artifacts.

## Run locally

From the repository root:

```bash
pip install -r codes/summary_app/requirements.txt
streamlit run codes/summary_app/app.py
```

Or from inside `codes/summary_app/`:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment

The app can be deployed from this folder as a standalone Streamlit app.
Because it is read-only, it does not require Supabase credentials.
The only optional configuration is a demo URL used for the "Launch 3-minute demo" button.


## Notes for the final submission

- This app is **supplementary** to the final paper and poster.
- The authoritative statistical outputs for the final submission are the script-generated figures/tables in `artifacts/`.
- The summary app is intended for interactive exploration and presentation, not as the primary reproducibility entrypoint.
