# Architecture

This document describes the modules, the data flow, the phase machine, the
database schema, and the randomization logic. Read this once and you can find
everything in the codebase.

---

## 1. Module map

```
┌────────────────────────────────────────────────────────────────────┐
│                           app.py                                   │
│   page config + session bootstrap + phase router                   │
└──┬──────────────┬─────────────────┬──────────────────┬─────────────┘
   │              │                 │                  │
   │              │                 │                  │
   ▼              ▼                 ▼                  ▼
screens.py   ui_components.py  experiment_logic.py   database.py
   │              │                 │                  │
   │              │                 │                  │
   └──────────────┴─────────────────┘                  │
                  │                                    │
                  ▼                                    ▼
              utils.py                          Supabase client
              (pure helpers)                    (PostgreSQL)
                  ▲
                  │
              config.py
              (constants, text, case data)
```

| Module                | Responsibility                                                                                   |
| --------------------- | ------------------------------------------------------------------------------------------------ |
| `app.py`              | One entry point. Establish `session_id`, resume or start, and dispatch to the screen for the current phase. No business logic. |
| `config.py`           | All constants and user-facing text — cost params, the 18 + 2 cases, protocol rotation, consent / glossary / instructions text, quiz questions, performance-tier messages. |
| `database.py`         | All Supabase reads and writes. Wraps the client and retries each call once on transient error before raising. |
| `ui_components.py`    | Reusable visual components: case card (with deterministic per-participant template variation), AI panel, decision buttons, probability sliders (mandatory + prefilled), submit button (with review-time gate), Step-1 summary card, feedback card. Holds the page CSS. |
| `screens.py`          | One function per phase. Reads from / writes to `st.session_state`, calls `database.py` to persist, and calls `_set_phase(...)` to advance. |
| `experiment_logic.py` | Group assignment, deterministic within-block randomization, full trial-sequence construction, performance scoring, quiz scoring. Pure functions. |
| `utils.py`            | Stateless helpers: timing (`now_ms`), deterministic seed (`stable_seed`), display formatters, optimal-decision logic, performance-tier classifier. |

`config.py` is imported widely. Nothing imports `screens.py` except `app.py`,
and `screens.py` is the only module that touches `database.py` *and*
`ui_components.py` together.

---

## 2. Data flow for a single trial

This is the path a participant's response takes from click to database row.

```
1. screens.trial_screen() renders the case card and decision controls.
   The case card uses one of 3 equivalent opening templates, chosen
   deterministically from md5(participant_id, case_id) — same participant
   sees same phrasing on reload; different participants see variants.
2. Participant clicks APPROVE / REJECT.
   → ui_components.render_decision_buttons() updates st.session_state[f"trial_{idx}_decision_*"] and st.rerun().
3. Participant moves the probability select_slider.
   → Streamlit updates the widget's session_state key automatically.
4. Participant clicks "Submit decision".
   → ui_components.submit_button_with_gate() checks: decision set? prob set? ≥5s elapsed? On all yes, returns True.
5. screens._save_trial_row() builds the trial dict from session_state and the case fixture, and calls database.insert_trial().
6. database.insert_trial() does an upsert keyed on (participant_id, trial_index) so a retry never duplicates.
7. screens._advance_after_trial() decides the next phase:
       practice  → "practice_feedback"
       end of practice / block / experiment → block_intro / reflection as appropriate
       otherwise → next "trial".
8. screens._set_phase() also writes (participant_id, current_phase, current_trial_index) to the participants row, so a refresh resumes here.
```

For the `human_first` protocol the same pipeline runs in two halves
(`_render_human_first_step1` then `_render_human_first_step2`), and the trial
row is only written after Step 2.

---

## 3. State machine

`st.session_state.phase` drives `app.py`'s `PHASE_ROUTER`.

```
                          (start)
                             │
                             ▼
                         consent ─────────► (creates participant row)
                             │
                             ▼
                       demographics ──────► (updates row)
                             │
                             ▼
                          glossary
                             │
                             ▼
                            quiz
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
         (pass ≥2)    (fail, attempt 1)  (fail, attempt 2)
              │              │              │
              │              ▼              ▼
              │         quiz_retry      quiz_failed  (terminal)
              │              │
              │              ├── pass ──┐
              │              │          │
              │              ▼          │
              │         quiz_failed     │
              │                         │
              ▼                         ▼
       practice_intro ◄─────────────────┘
              │
              ▼
      trial(-2) ─► practice_feedback ─► trial(-1) ─► practice_feedback
              │
              ▼
       block_intro(block_1) ─► trial(1) … trial(6)
              │
              ▼
       block_intro(block_2) ─► trial(7) … trial(12)
              │
              ▼
       block_intro(block_3) ─► trial(13) … trial(18)
              │
              ▼
          reflection ─────► (updates row: self_reported_reliance,
              │               ai_surprise_strategy)
              ▼
            trust
              │
              ▼
         performance ──────► (updates row: trust_rating, total_cost,
              │               optimal_cost, completed=true)
              ▼
          thank_you  (terminal)
```

Resumption: when the app loads, `app._resume_or_start()` reads
`current_phase` and `current_trial_index` from the participant row and re-enters
exactly here. The trial sequence is rebuilt deterministically from
`(participant_id, group)` so the cases the participant saw before are the
cases they see now.

---

## 4. Database schema

See `setup_supabase.sql` for the canonical definition. Summary:

### `participants`
| Column                 | Type        | Notes                                                                           |
| ---------------------- | ----------- | ------------------------------------------------------------------------------- |
| `id`                   | UUID PK     | Foreign-key target for `trials` and `quiz_responses`.                           |
| `participant_number`   | SERIAL      | Drives round-robin group assignment; created server-side for atomicity.         |
| `participant_group`    | TEXT        | `group_1` \| `group_2` \| `group_3`.                                            |
| `age_range`            | TEXT        | One of `AGE_RANGES` from config.                                                |
| `education`            | TEXT        | One of `EDUCATION_LEVELS` from config.                                          |
| `consent_timestamp`    | TIMESTAMPTZ | Default `now()` at insert.                                                      |
| `started_at`           | TIMESTAMPTZ | Default `now()` at insert.                                                      |
| `completed_at`         | TIMESTAMPTZ | Set when the experiment finishes.                                               |
| `completed`            | BOOLEAN     | Used by retake-prevention check.                                                |
| `trust_rating`         | INTEGER     | 1–5, set on the trust screen.                                                   |
| `self_reported_reliance` | TEXT      | One of `Never`/`Rarely`/`Sometimes`/`Often`/`Always`. Self-reported rate of changing mind after seeing AI advice. |
| `ai_surprise_strategy` | TEXT        | Self-reported strategy when AI prediction surprised participant.                |
| `total_cost`           | FLOAT       | Total participant loss across the 18 experimental trials (in dollars).          |
| `optimal_cost`         | FLOAT       | Total loss the cost-optimal strategy would have incurred on the same 18 cases. |
| `session_id`           | TEXT        | UUID stored in the `?s=` URL param.                                             |
| `current_trial_index`  | INTEGER     | For session resumption: -2/-1 practice, 1..18 experimental, 0 pre-practice.     |
| `current_phase`        | TEXT        | Last screen the participant reached.                                            |

### `trials`
| Column                  | Type      | Notes                                                                |
| ----------------------- | --------- | -------------------------------------------------------------------- |
| `id`                    | UUID PK   |                                                                      |
| `participant_id`        | UUID FK   | Cascade delete from participants.                                    |
| `trial_index`           | INTEGER   | -2, -1 practice; 1..18 experimental.                                 |
| `case_id`               | INTEGER   | Stable identifier from the fixture in `config.EXPERIMENTAL_CASES`.   |
| `case_position`         | INTEGER   | Original ordinal of the case in the fixture.                         |
| `block`                 | TEXT      | `practice` \| `block_1` \| `block_2` \| `block_3`.                   |
| `protocol`              | TEXT      | `no_ai` \| `ai_first` \| `human_first`.                              |
| `difficulty_tier`       | TEXT      | `easy` \| `medium` \| `hard` (from fixture).                         |
| `difficulty_score`      | FLOAT     | From fixture.                                                        |
| `y_true`                | INTEGER   | 1 = default, 0 = repaid.                                             |
| `pred_prob`             | FLOAT     | Model-predicted probability of default.                              |
| `model_correct`         | INTEGER   | 1 if the model's class at 0.5 threshold matches `y_true`.            |
| `model_optimal`         | INTEGER   | 1 if the model's 0.5 decision matches the cost-optimal TAU decision. |
| `decision_init`         | INTEGER   | Step-1 approve(1)/reject(0). NULL for `no_ai` and `ai_first`.        |
| `prob_estimate_init`    | FLOAT     | Step-1 probability. NULL for `no_ai` and `ai_first`.                 |
| `time_to_init_ms`       | INTEGER   | Time from trial load to Step-1 submit. NULL for non-human-first.     |
| `decision_final`        | INTEGER   | Final approve(1)/reject(0). Always populated.                        |
| `prob_estimate_final`   | FLOAT     | Final probability in [0, 1]. Always populated.                       |
| `confidence`            | INTEGER   | Legacy column. No longer collected; always NULL on new runs.          |
| `time_to_final_ms`      | INTEGER   | Time from final-step load to final-step submit.                      |
| `total_trial_ms`        | INTEGER   | Time from trial load to final submit.                                |
| `created_at`            | TIMESTAMPTZ| Default `now()`.                                                    |
| **UNIQUE**              |           | `(participant_id, trial_index)` — prevents duplicate submits.        |

### `quiz_responses`
One row per question per attempt. Fields: `id, participant_id, attempt (1|2),
question_id (1..3), selected_answer (A..D), is_correct, created_at`.

---

## 5. Randomization

### Group assignment (round-robin)
`participant_number` is a Postgres `SERIAL`; it is generated atomically server-side
when the participant row is inserted. `experiment_logic.assign_group()` then
maps it to a group:

```python
["group_1", "group_2", "group_3"][(participant_number - 1) % 3]
```

Two participants who hit `consent → Continue` simultaneously still receive
distinct numbers and therefore distinct (round-robin) groups.

### Within-block ordering (deterministic shuffle)
Each block has 6 cases. The presentation order within a block is shuffled
**per participant** but reproducible:

```python
seed = int(md5(f"{participant_id}:{block_name}").hexdigest(), 16) % 2**32
random.Random(seed).shuffle(cases)
```

Reproducibility matters because a participant who refreshes mid-block must see
the same case order they saw before. Python's built-in `hash()` is randomized
per process, so it cannot be used for this — `utils.stable_seed` uses
hashlib instead.

### Block ordering
Blocks are always presented in order `block_1 → block_2 → block_3`. The
*protocol* applied to each block is determined by the participant's group via
`config.PROTOCOL_ROTATION`, a 3×3 Latin square so every protocol appears
exactly once in each position across the three groups.

### Practice trials
Practice trials are `trial_index = -2` and `-1`. They always use the
`ai_first` protocol (set in `config.PRACTICE_PROTOCOL`) so the participant sees
the AI panel before encountering the more complex `human_first` flow. Practice
trials are stored in the `trials` table but excluded from the performance
score.

