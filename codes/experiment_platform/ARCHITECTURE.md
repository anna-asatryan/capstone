# Experiment Platform Architecture

This document describes the Streamlit experiment platform, its module structure, database flow, state machine, frozen inputs, and randomization logic.

The platform implements the participant-facing experiment for the loan decision study. It uses Streamlit for the web interface and Supabase/PostgreSQL for persistent server-side storage.

---

## 1. Module Map

```text
┌────────────────────────────────────────────────────────────────────┐
│                              app.py                                │
│   Streamlit page config + session bootstrap + phase router         │
└──┬──────────────┬─────────────────┬──────────────────┬─────────────┘
   │              │                 │                  │
   ▼              ▼                 ▼                  ▼
screens.py   ui_components.py  experiment_logic.py   database.py
   │              │                 │                  │
   │              │                 │                  ▼
   └──────────────┴─────────────────┘              Supabase
                  │                                PostgreSQL
                  ▼
              utils.py
                  ▲
                  │
              config.py
       constants, text, cost values,
       frozen case/protocol loading
```

| Module | Responsibility |
| --- | --- |
| `app.py` | Main Streamlit entrypoint. Sets page configuration, initializes/resumes session state, and dispatches to the correct screen based on the current phase. |
| `config.py` | Experiment constants, user-facing text, cost parameters, quiz questions, and loading of locked case/protocol CSVs from `data/frozen/`. |
| `database.py` | All Supabase reads/writes. Provides participant, trial, quiz, reflection, trust, completion, and resume operations. Demo mode bypasses writes. |
| `screens.py` | One function per participant-facing phase: consent, demographics, glossary, quiz, practice, trial, reflection, trust, performance, thank-you, and demo screens. |
| `ui_components.py` | Reusable UI components: case cards, AI panel, decision buttons, probability sliders, submit gates, feedback cards, CSS, and layout helpers. |
| `experiment_logic.py` | Pure experiment logic: group assignment, deterministic trial sequence construction, practice/demo sequence construction, quiz scoring, and cost/performance scoring. |
| `utils.py` | Stateless helpers: timing, deterministic seed generation, display formatting, optimal-decision logic, performance-tier classification, and demo-mode detection. |

`app.py` is the only public Streamlit entrypoint. `database.py` centralizes persistence. `config.py` should be the only place where experiment-wide constants and user-facing text are changed.

---

## 2. Frozen Experiment Inputs

The app does not manually embed the experimental case set. Instead, `config.py` loads locked CSVs from:

```text
data/frozen/final_cases.csv
data/frozen/practice_cases.csv
data/frozen/protocol_rotation.csv
```

These files define the deployed experiment:

- `final_cases.csv`: 18 scored cases
- `practice_cases.csv`: 2 practice cases
- `protocol_rotation.csv`: Latin-square mapping from participant group to block protocol

This design keeps the deployed Streamlit app synchronized with the project-level frozen artifacts. The platform copy should match the validated files under the project-level `artifacts/frozen/` directory.

---

## 3. Data Flow for a Trial

This is the path from participant interaction to a database row.

```text
1. screens.trial_screen() renders the case and the correct protocol UI.
2. ui_components.py captures decisions and probability estimates through Streamlit widgets.
3. For no_ai and ai_first, the final decision/probability are submitted once.
4. For human_first, Step 1 stores the initial decision/probability in session state;
   Step 2 reveals the AI panel and collects the final decision/probability.
5. screens._save_trial_row() builds the trial row from session state and the frozen case fixture.
6. database.insert_trial() upserts the row into Supabase using (participant_id, trial_index).
7. screens._advance_after_trial() moves to practice feedback, the next trial, the next block,
   reflection, or completion depending on the current position.
8. screens._set_phase() writes current_phase and current_trial_index to the participant row,
   allowing refresh/resume behavior.
```

The upsert key `(participant_id, trial_index)` prevents duplicate trial rows if a participant refreshes or a transient database retry occurs.

---

## 4. State Machine

`st.session_state.phase` drives the app routing.

```text
(start)
   │
   ▼
consent ───────► creates participant row
   │
   ▼
demographics ─► updates age/education
   │
   ▼
glossary
   │
   ▼
quiz
   ├── pass ───────────────► practice_intro
   ├── fail attempt 1 ─────► quiz_retry ─► quiz
   └── fail attempt 2 ─────► quiz_failed

practice_intro
   │
   ▼
trial(-2) ─► practice_feedback ─► trial(-1) ─► practice_feedback
   │
   ▼
block_intro(block_1) ─► trial(1)  … trial(6)
   │
   ▼
block_intro(block_2) ─► trial(7)  … trial(12)
   │
   ▼
block_intro(block_3) ─► trial(13) … trial(18)
   │
   ▼
reflection ─► trust ─► performance ─► thank_you
```

Resumption uses `current_phase` and `current_trial_index` stored in the `participants` row. The trial sequence is rebuilt deterministically from participant id and group, so a refreshed participant returns to the same trial order.

---

## 5. Demo Mode

Demo mode exists for demonstration and dashboard-linking purposes. It is detected in `utils.is_demo_mode()` through one of the following:

- URL query parameter: `?demo=true`
- Streamlit secret: `demo_mode = true`
- environment variable: `DEMO_MODE=true`

In demo mode:

- `app.py` initializes a synthetic participant (`demo_user`)
- `experiment_logic.build_demo_trial_sequence()` returns three curated demo trials
- `database.py` bypasses Supabase writes and keeps demo responses in session state
- the demo ends at `demo_end` instead of writing a completed study record

Demo mode should not be used for real participants.

---

## 6. Database Schema

The canonical schema is defined in:

```text
queries/1_setup_supabase.sql
```

If upgrading an older deployment that lacks reflection columns, use:

```text
queries/2_migration_add_reflection.sql
```

### `participants`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | Participant identifier used as FK in trial/quiz tables. |
| `participant_number` | SERIAL | Server-side sequence; used for round-robin group assignment. |
| `participant_group` | TEXT | `group_1`, `group_2`, or `group_3`. |
| `age_range` | TEXT | Demographic category from `config.AGE_RANGES`. |
| `education` | TEXT | Demographic category from `config.EDUCATION_LEVELS`. |
| `consent_timestamp` | TIMESTAMPTZ | Consent/creation timestamp. |
| `started_at` | TIMESTAMPTZ | Start timestamp. |
| `completed_at` | TIMESTAMPTZ | Set at completion. |
| `completed` | BOOLEAN | Used to identify completed participants. |
| `trust_rating` | INTEGER | 1–5 trust rating collected near the end. |
| `self_reported_reliance` | TEXT | Self-reported frequency of changing mind after seeing AI advice. |
| `ai_surprise_strategy` | TEXT | Self-reported strategy when AI was surprising. |
| `total_cost` | FLOAT | Participant cost across scored trials. |
| `optimal_cost` | FLOAT | Cost of model-threshold optimal strategy on the same cases. |
| `session_id` | TEXT | Session token used for resumption. |
| `current_trial_index` | INTEGER | `-2`, `-1`, `1..18`, or pre/post-trial state. |
| `current_phase` | TEXT | Last screen reached. |

### `trials`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | Trial row id. |
| `participant_id` | UUID FK | References `participants.id`. |
| `trial_index` | INTEGER | `-2`, `-1` for practice; `1..18` for scored trials. |
| `case_id` | INTEGER | Stable case id from the frozen fixture. |
| `case_position` | INTEGER | Original case order in the frozen fixture. |
| `block` | TEXT | `practice`, `block_1`, `block_2`, `block_3`, or `demo`. |
| `protocol` | TEXT | `no_ai`, `ai_first`, or `human_first`. |
| `difficulty_tier` | TEXT | `easy`, `medium`, or `hard`. |
| `difficulty_score` | FLOAT | Case-design difficulty score. |
| `y_true` | INTEGER | `1 = default`, `0 = repaid`. |
| `pred_prob` | FLOAT | AI predicted default probability. |
| `model_correct` | INTEGER | Whether the model class at 0.5 matches `y_true`. |
| `model_optimal` | INTEGER | Whether the 0.5 model decision agrees with the cost-sensitive decision. |
| `decision_init` | INTEGER | Human-first initial decision; null otherwise. |
| `prob_estimate_init` | FLOAT | Human-first initial probability; null otherwise. |
| `time_to_init_ms` | INTEGER | Time to Step-1 submit in human-first. |
| `decision_final` | INTEGER | Final approve/reject decision. |
| `prob_estimate_final` | FLOAT | Final probability estimate in `[0,1]`. |
| `confidence` | INTEGER | Legacy column; no longer collected in the current UI. |
| `time_to_final_ms` | INTEGER | Time to final submit. |
| `total_trial_ms` | INTEGER | Full trial duration. |
| `created_at` | TIMESTAMPTZ | Insert timestamp. |

`trials` has a uniqueness constraint on `(participant_id, trial_index)`.

### `quiz_responses`

One row per quiz question per attempt:

```text
id, participant_id, attempt, question_id, selected_answer, is_correct, created_at
```

---

## 7. Randomization and Counterbalancing

### Group assignment

`participant_number` is generated atomically by PostgreSQL. `experiment_logic.assign_group()` maps it to a group:

```python
["group_1", "group_2", "group_3"][(participant_number - 1) % 3]
```

This gives round-robin assignment across the three Latin-square groups.

### Block ordering

Blocks are always shown as:

```text
block_1 → block_2 → block_3
```

The protocol assigned to each block depends on participant group and is loaded from `data/frozen/protocol_rotation.csv` into `config.PROTOCOL_ROTATION`.

### Within-block case order

Each block contains six cases. Their order is shuffled per participant using a deterministic seed derived from the participant id and block name. This allows refresh/resume without changing the case order.

Python's built-in `hash()` is not used because it is randomized per process. Stable hashing is handled through `utils.stable_seed()`.

### Practice trials

Practice trials use `trial_index = -2` and `-1`. They are stored in the database but excluded from the scored analysis. They use `config.PRACTICE_PROTOCOL`, currently `ai_first`, so participants encounter the AI panel before the more complex human-first flow.

---

## 8. Supabase Access and Security Model

The app is intended to access Supabase from the Streamlit server using credentials stored in Streamlit secrets. This is appropriate for the controlled academic deployment used in the study.

Security notes:

- `.streamlit/secrets.toml` must remain local-only and must never be committed or submitted.
- `.streamlit/secrets.toml.template` is safe to track.
- If `secrets.toml` or a Supabase key is accidentally shared, rotate the key.
- The SQL schema and RLS settings are suitable for this controlled server-side Streamlit deployment; they should be reviewed before adapting the platform for a public client-side application.

---

## 9. Post-Collection Exports

Post-collection exports are produced from Supabase using SQL queries documented in `README.md`. The exported files used by the analysis layer are stored at the project level:

```text
data/experiment_exports/participants.csv
data/experiment_exports/trials.csv
data/experiment_exports/quiz_responses.csv
```

These exports are not written by the participant-facing app itself; they are generated after data collection from the Supabase dashboard.