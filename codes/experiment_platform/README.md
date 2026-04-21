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
   - **anon public key**

> **Upgrading from an earlier version of this platform?** If your Supabase
> project was created before the reflection screen was added, run
> `migration_add_reflection.sql` (instead of the full schema) to add the two
> new columns without touching existing data.

### 3.2 Configure secrets
```bash
cd experiment_platform
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
```
Edit `.streamlit/secrets.toml` and paste in your Supabase URL and anon key.
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
   anon_key = "YOUR-ANON-KEY"
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

---

## 6. Modifying the experiment

| What you want to change           | Where (file → variable)                                            |
| --------------------------------- | ------------------------------------------------------------------ |
| Cases (the 18 + 2 practice)       | `config.py` → `EXPERIMENTAL_CASES`, `PRACTICE_CASES`               |
| Cost parameters                   | `config.py` → `C_FN`, `C_FP` (TAU is recomputed)                   |
| Minimum review time per trial     | `config.py` → `MIN_TRIAL_TIME_MS`                                  |
| Latin-square protocol rotation    | `config.py` → `PROTOCOL_ROTATION`                                  |
| Practice protocol                 | `config.py` → `PRACTICE_PROTOCOL`                                  |
| Consent / instructions / glossary | `config.py` → `CONSENT_TEXT`, `GLOSSARY_TEXT`, `INSTRUCTIONS_TEXT` |
| Quiz questions or pass threshold  | `config.py` → `QUIZ_QUESTIONS`, `QUIZ_PASS_THRESHOLD`              |
| Per-block intro wording           | `config.py` → `BLOCK_HEADERS`                                      |
| Trust rating wording              | `config.py` → `TRUST_QUESTION`, `TRUST_LABELS`                     |
| Reflection questions              | `config.py` → `REFLECTION_INTRO`, `RELIANCE_QUESTION`, `RELIANCE_OPTIONS`, `SURPRISE_QUESTION`, `SURPRISE_OPTIONS` |
| Performance-tier messages         | `config.py` → `PERFORMANCE_MESSAGES` (and `utils.performance_tier`)|
| Card / AI panel styling           | `ui_components.py` → `PAGE_CSS`                                    |
| Case prose template               | `ui_components.py` → `render_case_card`                            |
| Database schema                   | `database.py` + `setup_supabase.sql` (rerun the SQL)               |

After editing `config.py` you only need to restart the Streamlit process; no
schema migration is required unless you change the database tables.

---

## 7. Testing checklist

Manual run-through to perform before sharing the URL with participants. Open a
private/incognito window for each run so the `?s=…` session cookie doesn't
leak.

- [ ] Open the app in 3 fresh incognito tabs in succession. The
      `participant_number` of each (visible in Supabase) should be N, N+1, N+2,
      and the assigned `participant_group` should rotate group_1 → group_2 →
      group_3 → group_1.
- [ ] Decline consent — verify nothing is written to Supabase.
- [ ] Accept consent, complete demographics. Confirm the participant row in
      Supabase now has `age_range` and `education`.
- [ ] On the comprehension quiz, deliberately answer all three wrong.
      Confirm the retry message appears, the instructions are re-shown, and
      that 3 rows are inserted into `quiz_responses` with `attempt = 1`.
- [ ] Fail the quiz a second time. Confirm the polite-exit screen appears
      and 3 more `quiz_responses` rows exist with `attempt = 2`.
- [ ] In a fresh tab: pass the quiz on attempt 1 and complete the practice.
      Verify both feedback screens explain the outcome correctly.
- [ ] During an `ai_first` block: verify the AI panel appears **before** the
      decision controls.
- [ ] During a `human_first` block: verify Step 1 is locked into a summary
      after submission, the AI panel is then shown, and the Step 2 probability
      slider is pre-filled with the Step 1 value.
- [ ] During a `no_ai` block: verify no AI panel is rendered.
- [ ] Try to submit a trial without setting the probability — submit should
      stay disabled.
- [ ] Try to submit within 5 seconds of a trial loading — a "review for X
      more seconds" caption should appear, and the submission should not
      register.
- [ ] Refresh the page mid-block. Verify the URL still has `?s=…` and that
      the app resumes at the correct trial.
- [ ] Refresh the page after completing the experiment. Verify the
      "already completed" screen appears.
- [ ] On a phone: confirm the case card text wraps and the buttons stretch
      to full width without overflow.
- [ ] After completion, confirm `participants.total_cost` and
      `optimal_cost` are populated, and that there are exactly 18 rows in
      `trials` for that participant (practice trials are also stored, so the
      true count is 20 per participant).

---
