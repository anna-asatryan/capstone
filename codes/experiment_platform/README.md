# Experiment Platform — Loan Decision Study

A Streamlit-based behavioral experiment platform for studying how the **timing of AI advice** affects decision quality 
in a cost-sensitive loan-approval task.

Participants review loan applications and make approval/rejection decisions under three interaction protocols:

- `no_ai`: participant decides without AI assistance
- `ai_first`: AI probability and recommendation are shown before the participant decides
- `human_first`: participant gives an initial judgment, then sees AI advice, then gives a final judgment

The platform uses **Streamlit** for the participant-facing web app and **Supabase/PostgreSQL** for server-side persistence.

- **Stack:** Streamlit (Python) + Supabase (PostgreSQL)
- **Deployment target:** Streamlit Community Cloud
- **Per-participant time:** ~15 minutes
- **Trials per participant:** 2 practice + 18 experimental

---


## 1. What participants do

```
                                         per participant
       ┌──────────────────────────────────────────────────────────┐
Browser│ consent → demographics → glossary+instructions → quiz    │
       │   → 2 practice trials (with feedback)                    │
       │   → block_1 (6 trials) → block_2 (6) → block_3 (6)       │
       │   → reflection (2 self-report questions) → trust rating  │
       │   → performance summary → thank you                      │
       └──────────────────────────────────────────────────────────┘
                                  │
              writes every action │
                                  ▼
                           ┌──────────────┐
                           │   Supabase   │
                           │  Postgres DB │
                           └──────────────┘
```

Within each block of 6 trials, all 6 cases are run under one of three protocols:

| Protocol     | UI flow                                                                |
| ------------ | ---------------------------------------------------------------------- |
| `no_ai`      | Case → decision + probability → submit                                 |
| `ai_first`   | Case + AI panel → decision + probability → submit                      |
| `human_first`| Case → initial decision + probability → submit → AI panel → final decision + probability → submit |

Each participant sees all three protocols exactly once, in an order determined
by a Latin-square rotation (`group_1`, `group_2`, `group_3`). Group is assigned
round-robin by participant number.

---

## 2. Current Repository Layout

```text
experiment_platform/
├── app.py                         # Streamlit entrypoint and phase router
├── config.py                      # constants, text, quiz, cost values, and frozen case/protocol loading
├── database.py                    # all Supabase read/write operations
├── experiment_logic.py            # group assignment, deterministic trial sequence, scoring
├── screens.py                     # one function per app screen/phase
├── ui_components.py               # reusable UI components and CSS
├── utils.py                       # pure helpers and demo-mode detection
├── main.py                        # optional wrapper entrypoint, if used
├── README.md                      # this file
├── ARCHITECTURE.md                # module/data-flow documentation
├── requirements.txt               # pip dependencies
├── pyproject.toml                 # project metadata / uv config
├── uv.lock                        # locked environment from uv
├── .gitignore
├── .streamlit/
│   ├── config.toml                # Streamlit theme/config
│   └── secrets.toml.template      # template only; never commit secrets.toml
├── data/
│   └── frozen/
│       ├── final_cases.csv        # locked 18 scored cases
│       ├── practice_cases.csv     # locked 2 practice cases
│       └── protocol_rotation.csv  # locked Latin-square protocol rotation
├── queries/
│   ├── 1_setup_supabase.sql       # initial database schema and policies
│   └── 2_migration_add_reflection.sql
└── scripts/
    ├── db_notebook_utils.py       # helper functions for notebook/database inspection
    └── db_report.py               # read-only Supabase audit/export CLI
```

Important implementation detail: `config.py` loads the locked cases and protocol rotation from `data/frozen/`. Case data are **not manually embedded** in the code. The source of truth for deployed experiment stimuli is the frozen CSV snapshot.

---

## 3. Frozen Experiment Inputs

The platform expects the following files to exist:

```text
data/frozen/final_cases.csv
data/frozen/practice_cases.csv
data/frozen/protocol_rotation.csv
```

These files are copied from the project-level frozen artifacts and define the official participant-facing experiment:

- `final_cases.csv`: 18 scored loan cases
- `practice_cases.csv`: 2 practice cases
- `protocol_rotation.csv`: assignment of protocols to blocks for `group_1`, `group_2`, and `group_3`

Do not edit these files manually. If the case design changes, regenerate/validate the frozen artifacts from the upstream case-design workflow and then sync the validated frozen CSVs into this folder.

---

## 4. Local Setup

### 4.1 Create Supabase schema

Create a Supabase project, open the SQL editor, and run:

```text
queries/1_setup_supabase.sql
```

This creates the core tables, indexes, constraints, and Row-Level-Security policies used by the app.

If upgrading an older Supabase project that already had the original schema but not the reflection fields, run:

```text
queries/2_migration_add_reflection.sql
```

Do not run the migration as a substitute for the full setup on a fresh database.

### 4.2 Configure Streamlit secrets

From inside `codes/experiment_platform/`:

```bash
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` with the Supabase project URL and server-side key.

```toml
[supabase]
url = "https://YOUR-PROJECT-REF.supabase.co"
secret_key = "YOUR-SERVER-SIDE-KEY"
```

Security rule:

- `.streamlit/secrets.toml` is local-only and must never be committed or included in a submission archive.
- Only `.streamlit/secrets.toml.template` should be tracked.
- If `secrets.toml` is accidentally shared, rotate the Supabase key immediately.

### 4.3 Install dependencies and run locally

```bash
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## 5. Deployment to Streamlit Community Cloud

1. Push the cleaned platform directory to a GitHub repository.
2. Create a new Streamlit Community Cloud app.
3. Set the app entrypoint to:

```text
app.py
```

4. Add secrets in **Advanced settings → Secrets**:

```toml
[supabase]
url = "https://YOUR-PROJECT-REF.supabase.co"
secret_key = "YOUR-SERVER-SIDE-KEY"
```

5. Deploy and share the generated URL with participants.

The participant-facing app accesses Supabase server-side through Streamlit secrets. Supabase credentials should never be exposed in client-side code, screenshots, GitHub, or submission archives.

---

## 6. Demo Mode

The platform includes a demo mode for showing the interaction flow without storing study responses in Supabase.

Demo mode can be enabled by:

- URL query parameter: `?demo=true`
- Streamlit secret: `demo_mode = true`
- environment variable: `DEMO_MODE=true`

In demo mode:

- the app uses a synthetic participant id (`demo_user`)
- only three curated trials are shown
- trial responses are kept in Streamlit session state
- database writes are bypassed

---

## 7. Post-Collection Data Export from Supabase

After data collection, export the database tables from Supabase using the SQL editor and the result-panel **Download → CSV** option.

### Completed participants

```sql
SELECT *
FROM participants
WHERE completed = TRUE
ORDER BY started_at;
```

### Completed participants with trial rows

```sql
SELECT p.participant_number, p.participant_group, p.age_range, p.education,
       p.trust_rating, p.self_reported_reliance, p.ai_surprise_strategy,
       p.total_cost, p.optimal_cost,
       t.*
FROM trials t
JOIN participants p ON p.id = t.participant_id
WHERE p.completed = TRUE
ORDER BY p.participant_number, t.trial_index;
```

### Quiz attempts

```sql
SELECT p.participant_number, q.*
FROM quiz_responses q
JOIN participants p ON p.id = q.participant_id
ORDER BY p.participant_number, q.attempt, q.question_id;
```

The exported CSVs should be stored at the project level under:

```text
data/experiment_exports/participants.csv
data/experiment_exports/trials.csv
data/experiment_exports/quiz_responses.csv
```

These exports are then used by the analysis notebook and final reproduction scripts.

---

## 8. Development Notes

- `app.py` is the Streamlit app entrypoint.
- `config.py` contains experiment constants, user-facing text, quiz content, cost parameters, and loads frozen cases/protocol rotation from `data/frozen/`.
- `database.py` is the only module that should perform Supabase reads/writes.
- `experiment_logic.py` contains deterministic group assignment, block randomization, trial sequence generation, and scoring logic.
- `screens.py` implements the app phase machine.
- `ui_components.py` contains reusable display components.
- `utils.py` contains stateless helpers and demo-mode detection.



