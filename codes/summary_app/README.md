# Summary App — Human-AI Decision Explorer

This folder replaces the old `codes/summary_app` with an interactive poster companion app.
It is intentionally **not** a copy of the poster. The poster gives the compressed story; this app lets judges inspect the evidence in more depth.

## What it shows

- **Overview**: headline protocol results and main behavioral findings.
- **Protocol Comparator**: cost, accuracy, Brier score, AI-distance, and carryover sensitivity.
- **Human-First Revision**: initial → final decision switch matrix and Sankey flow.
- **Reliance Explorer**: WOA distribution, zero-inflation, reliance decomposition, participant heterogeneity.
- **Case Explorer**: case-level outcomes for each loan stimulus.
- **Platform Demo**: optional link to a safe demo version of the behavioral platform.

## Expected repo location

Place this folder at:

```text
codes/summary_app/
```

The app locates the capstone repo root by searching upward for `artifacts/`.
It reads:

```text
artifacts/db_exports/participants.csv
artifacts/db_exports/trials.csv
artifacts/db_exports/quiz_responses.csv
artifacts/frozen/final_cases.csv   # optional but recommended
artifacts/analysis/tables/ai_benefit_heterogeneity.csv  # optional
```

## Run locally

From the repo root:

```bash
pip install -r codes/summary_app/requirements.txt
streamlit run codes/summary_app/app.py
```

Or from inside `codes/summary_app`:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy

Deploy `codes/summary_app/app.py` on Streamlit Community Cloud from the repo or from a standalone synced repo.
Make sure the required `artifacts/` files are present in the deployed repository.

## Optional demo link

To show a button to the experiment platform demo, configure either:

```toml
# .streamlit/secrets.toml
demo_url = "https://your-demo-platform.streamlit.app"
```

or an environment variable:

```bash
SUMMARY_APP_DEMO_URL=https://your-demo-platform.streamlit.app
```

Do **not** link poster viewers to the real experiment platform unless it is in demo mode or uses a separate database/table.

## Design principles

- High contrast, light background, restrained palette.
- Minimal chart decoration; direct labels and clear axes.
- Cost is treated as the primary outcome; accuracy is secondary.
- The app avoids GitHub/paper links for the poster session because those deliverables are not finalized yet.
