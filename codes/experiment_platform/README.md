# Experiment Platform — Loan Decision Study

A behavioral-experiment web app for a research study on how the **timing of AI
advice** (shown before vs. after human judgment vs. not at all) affects decision
quality in a cost-sensitive loan-approval task.

- **Stack:** Streamlit (Python) + Supabase (PostgreSQL)
- **Deployment target:** Streamlit Community Cloud
- **Per-participant time:** ~15–20 minutes
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

## 2. Repository layout

```
experiment_platform/
├── app.py                           # entry point — page config + phase router
├── config.py                        # ALL constants and user-facing text
├── database.py                      # ALL Supabase reads/writes (with one retry)
├── ui_components.py                 # reusable UI: case card, AI panel, sliders…
├── screens.py                       # one function per screen (consent, trial, …)
├── experiment_logic.py              # group assignment, randomization, scoring
├── utils.py                         # pure helpers: timing, formatting, costs
├── requirements.txt
├── setup_supabase.sql               # complete schema + RLS policies (run ONCE)
├── migration_add_reflection.sql     # run if upgrading from an older schema
├── .streamlit/
│   ├── config.toml                  # theme (light)
│   └── secrets.toml.template        # copy to secrets.toml, fill in
├── .gitignore
├── README.md                        # this file
└── ARCHITECTURE.md                  # module-by-module data flow
```

If you only need to change wording, case data, or the quiz, you only need to
touch `config.py`.

---

## 3. Setup (local development)

### 3.1 Create a Supabase project
1. Go to [supabase.com](https://supabase.com) and create a new project.
2. Open the **SQL editor** and paste the entire contents of `setup_supabase.sql`.
   Run it once. This creates the tables (`participants`, `trials`,
   `quiz_responses`), indexes, and Row-Level-Security policies.
3. From **Project Settings → API**, copy two values:
   - **Project URL** (`https://<ref>.supabase.co`)
   - **secret key**

> **Upgrading from an earlier version of this platform?** If your Supabase
> project was created before the reflection screen was added, run
> `migration_add_reflection.sql` (instead of the full schema) to add the two
> new columns without touching existing data.

### 3.2 Configure secrets
```bash
cd experiment_platform
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
```
Edit `.streamlit/secrets.toml` and paste in your Supabase URL and secret key.
**Do not commit `secrets.toml`.**

### 3.3 Install + run
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`. A new participant record is created
the moment the user clicks **Continue** on the consent screen.

---

## 4. Deploy to Streamlit Community Cloud

1. Push this directory to a GitHub repository.
2. At [share.streamlit.io](https://share.streamlit.io) click **New app** and
   point it at your repo + branch + `app.py`.
3. Open **Advanced settings → Secrets** and paste:
   ```toml
   [supabase]
   url = "https://YOUR-PROJECT-REF.supabase.co"
   secret_key = "YOUR-SECRET-KEY"
   ```
4. Deploy. The public URL is what you share with participants.

The free tier sleeps after periods of inactivity. The first request after a
sleep takes ~10 s to wake. Participant data already in Supabase is unaffected.

---

## 5. Exporting data from Supabase

Open the **SQL editor** in your Supabase dashboard.

**All completed participants:**
```sql
SELECT *
FROM participants
WHERE completed = TRUE
ORDER BY started_at;
```

**All trials (with participant info):**
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

**All quiz attempts:**
```sql
SELECT p.participant_number, q.*
FROM quiz_responses q
JOIN participants p ON p.id = q.participant_id
ORDER BY p.participant_number, q.attempt, q.question_id;
```

Use the **Download → CSV** button on the result panel to export.