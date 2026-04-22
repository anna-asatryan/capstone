"""
One function per screen. Screens read from / write to st.session_state and
call into database.py for persistence. They never hold business logic
(protocol selection, scoring, randomization) — that lives in experiment_logic.

Phase machine:
  consent -> demographics -> glossary -> quiz -> [quiz_retry] -> practice_intro
  -> trial(-2) -> practice_feedback -> trial(-1) -> practice_feedback
  -> block_intro(block_1) -> trial(1..6)
  -> block_intro(block_2) -> trial(7..12)
  -> block_intro(block_3) -> trial(13..18)
  -> trust -> performance -> thank_you

Terminals: quiz_failed, already_completed.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from config import (
    AGE_RANGES,
    ALREADY_COMPLETED_TEXT,
    BLOCK_HEADERS,
    BLOCK_NUMBER,
    CONSENT_TEXT,
    DEMOGRAPHICS_INTRO,
    EDUCATION_LEVELS,
    EXPERIMENT_TITLE,
    GLOSSARY_TEXT,
    INSTRUCTIONS_TEXT,
    PERFORMANCE_MESSAGES,
    PRACTICE_INTRO,
    QUIZ_FAILED_WARNING,
    QUIZ_INTRO,
    QUIZ_KEY_POINTS,
    QUIZ_MAX_ATTEMPTS,
    QUIZ_PASS_THRESHOLD,
    QUIZ_QUESTIONS,
    QUIZ_RETRY_INTRO,
    REFLECTION_INTRO,
    RELIANCE_OPTIONS,
    RELIANCE_QUESTION,
    SURPRISE_OPTIONS,
    SURPRISE_QUESTION,
    THANK_YOU_TEXT,
    TRUST_LABELS,
    TRUST_QUESTION,
)
from database import (
    complete_participant,
    create_participant,
    get_participant_trials,
    insert_quiz_response,
    insert_trial,
    update_participant_demographics,
    update_participant_phase,
    update_participant_reflection,
)
from experiment_logic import (
    assign_group,
    build_trial_sequence,
    compute_performance,
    quiz_score,
)
from ui_components import (
    decision_label,
    inject_css,
    render_ai_panel,
    render_case_card,
    render_decision_buttons,
    render_feedback_card,
    render_locked_step1_summary,
    render_overall_progress,
    render_probability_slider_mandatory,
    render_probability_slider_prefilled,
    render_progress_line,
    render_response_card_header,
    render_sidebar_reference,
    render_step_divider,
    render_step_label,
    render_trial_header,
    submit_button_with_gate,
)
from utils import (
    format_currency,
    format_percent,
    now_ms,
    optimal_decision,
    performance_tier,
    trial_cost,
)


# =============================================================================
# Helpers shared across screens
# =============================================================================

def _set_phase(new_phase: str, trial_index: int | None = None) -> None:
    """Update phase in session + DB and rerun."""
    st.session_state.phase = new_phase
    if trial_index is not None:
        st.session_state.current_trial_index = trial_index
    pid = st.session_state.get("participant_id")
    if pid:
        try:
            update_participant_phase(
                pid, new_phase, st.session_state.get("current_trial_index")
            )
        except Exception:
            # Non-fatal: phase tracking is recovery-only; the trial table is the truth.
            pass
    st.rerun()


def _ensure_trial_sequence() -> list[dict[str, Any]]:
    if "trial_sequence" not in st.session_state:
        st.session_state.trial_sequence = build_trial_sequence(
            st.session_state.participant_id, st.session_state.participant_group
        )
    return st.session_state.trial_sequence


def _trial_at(idx: int) -> dict[str, Any]:
    seq = _ensure_trial_sequence()
    for t in seq:
        if t["trial_index"] == idx:
            return t
    raise KeyError(f"No trial with index {idx}")


def _block_position(seq: list[dict[str, Any]], idx: int, block: str) -> int:
    block_trials = [t for t in seq if t["block"] == block]
    for i, t in enumerate(block_trials):
        if t["trial_index"] == idx:
            return i + 1
    return 0


def _read_trial_final(idx: int) -> tuple[int | None, float | None]:
    """
    Read the just-submitted decision and probability for trial idx from
    session_state. The widget keys store the decision as 0/1 and the
    probability either as an int 0..100 or the sentinel string "—".
    Returns (None, None) if not set (e.g. after a page refresh).
    """
    decision = st.session_state.get(f"trial_{idx}_decision_final")
    prob_widget = st.session_state.get(f"trial_{idx}_prob_final")
    if decision is None or not isinstance(prob_widget, int):
        return None, None
    return int(decision), float(prob_widget) / 100.0


# =============================================================================
# Phase 1: Consent
# =============================================================================

def consent_screen() -> None:
    inject_css()
    st.title(EXPERIMENT_TITLE)
    st.markdown(CONSENT_TEXT)

    agreed = st.checkbox("I agree to participate.", key="consent_agreed")
    if st.button("Continue", type="primary", disabled=not agreed):
        try:
            row = create_participant(st.session_state.session_id)
        except Exception:
            st.error(
                "We couldn't create your participant record. Please refresh and try again."
            )
            return
        st.session_state.participant_id = row["id"]
        st.session_state.participant_number = row["participant_number"]
        st.session_state.participant_group = row["participant_group"] or assign_group(
            row["participant_number"]
        )
        _set_phase("demographics")


# =============================================================================
# Phase 2: Demographics
# =============================================================================

def demographics_screen() -> None:
    inject_css()
    st.title("Background")
    st.markdown(DEMOGRAPHICS_INTRO)

    age = st.selectbox(
        "Age range",
        options=AGE_RANGES,
        index=None,
        placeholder="Select…",
        key="dem_age",
    )
    edu = st.selectbox(
        "Education",
        options=EDUCATION_LEVELS,
        index=None,
        placeholder="Select…",
        key="dem_edu",
    )

    can_continue = age is not None and edu is not None
    if st.button("Continue", type="primary", disabled=not can_continue):
        try:
            update_participant_demographics(st.session_state.participant_id, age, edu)
        except Exception:
            st.error("We couldn't save your responses. Please try again.")
            return
        _set_phase("glossary")


# =============================================================================
# Phase 3: Glossary + Instructions
# =============================================================================

def glossary_screen() -> None:
    inject_css()
    st.title("Before you start")
    with st.expander("Key Terms You'll Need", expanded=True):
        st.markdown(GLOSSARY_TEXT)
    st.markdown(INSTRUCTIONS_TEXT)

    if st.button("I'm ready — continue to the comprehension check", type="primary"):
        _set_phase("quiz")


# =============================================================================
# Phase 4: Quiz (and retry)
# =============================================================================

def _render_quiz(attempt: int, intro: str) -> None:
    st.markdown(intro)
    answers: dict[int, str | None] = {}
    for q in QUIZ_QUESTIONS:
        opts = list(q["options"].keys())
        sel = st.radio(
            q["question"],
            options=opts,
            format_func=lambda x, q=q: f"{x}) {q['options'][x]}",
            index=None,
            key=f"quiz_a{attempt}_q{q['id']}",
        )
        answers[q["id"]] = sel
    all_set = all(a is not None for a in answers.values())
    if st.button("Submit answers", type="primary", disabled=not all_set):
        # Save every response, regardless of pass/fail
        pid = st.session_state.participant_id
        for q in QUIZ_QUESTIONS:
            sel = answers[q["id"]]
            try:
                insert_quiz_response(
                    pid,
                    attempt,
                    q["id"],
                    sel,
                    is_correct=(sel == q["correct"]),
                )
            except Exception:
                st.error(
                    "We couldn't save your answers. Please refresh and try again."
                )
                return
        score = quiz_score(answers, QUIZ_QUESTIONS)
        if score >= QUIZ_PASS_THRESHOLD:
            _set_phase("practice_intro")
            return
        if attempt < QUIZ_MAX_ATTEMPTS:
            _set_phase("quiz_retry")
        else:
            _set_phase("quiz_failed")


def quiz_screen() -> None:
    inject_css()
    st.title("Comprehension check")
    st.caption(QUIZ_INTRO)
    _render_quiz(attempt=1, intro="Please choose one answer per question.")


def quiz_retry_screen() -> None:
    inject_css()
    st.title("Comprehension check")
    st.warning(QUIZ_RETRY_INTRO)
    with st.expander("Review the instructions", expanded=True):
        st.markdown(INSTRUCTIONS_TEXT)
    _render_quiz(attempt=2, intro="Please answer all three questions again.")


def quiz_failed_screen() -> None:
    inject_css()
    st.title("A quick reminder before you continue")
    st.markdown(QUIZ_FAILED_WARNING)
    st.markdown(QUIZ_KEY_POINTS)
    if st.button("I understand — continue to the study", type="primary"):
        _set_phase("practice_intro")


# =============================================================================
# Phase 5: Practice intro + trial + feedback
# =============================================================================

def practice_intro_screen() -> None:
    inject_css()
    st.title("Practice")
    st.markdown(PRACTICE_INTRO)
    if st.button("Begin practice", type="primary"):
        st.session_state.current_trial_index = -2
        _set_phase("trial", trial_index=-2)


def practice_feedback_screen() -> None:
    inject_css()
    idx = st.session_state.current_trial_index
    trial = _trial_at(idx)
    case = trial["case"]

    decision, prob = _read_trial_final(idx)
    if decision is None or prob is None:
        # Resumed mid-feedback after a refresh; the data is in DB.
        try:
            db_trials = get_participant_trials(st.session_state.participant_id)
        except Exception:
            _advance_after_practice()
            return
        db_trial = next((t for t in db_trials if t["trial_index"] == idx), None)
        if not db_trial:
            _advance_after_practice()
            return
        decision = db_trial["decision_final"]
        prob = db_trial["prob_estimate_final"]

    y = case["y_true"]
    pred = case["pred_prob"]

    your_cost = trial_cost(decision, y)
    opt_dec = optimal_decision(pred)
    opt_cost = trial_cost(opt_dec, y)
    is_optimal = your_cost == opt_cost

    outcome_text = "**defaulted on the loan**" if y == 1 else "**repaid the loan**"
    your_dec_text = decision_label(decision)
    opt_dec_text = decision_label(opt_dec)
    pred_pct = format_percent(pred)

    if is_optimal and y == 1:
        explanation = (
            f"Your rejection avoided a $5,000 loss. The AI's {pred_pct} default "
            "estimate aligned with the actual outcome."
        )
    elif is_optimal and y == 0:
        explanation = (
            f"Approving was the cost-minimizing decision. With only a {pred_pct} default "
            "estimate, the expected loss from rejection ($1,000) exceeded the expected "
            "loss from approval."
        )
    elif decision == 1 and y == 1:
        explanation = (
            f"With a {pred_pct} predicted chance of default, **rejection** would have "
            "avoided the **$5,000** default loss."
        )
    else:
        # decision == 0 and y == 0
        explanation = (
            f"With only a {pred_pct} predicted chance of default, **approval** would "
            "have been optimal and saved the **$1,000** rejection cost."
        )

    st.title("Practice feedback")
    body = (
        f"<p><b>Outcome:</b> The borrower {outcome_text}.</p>"
        f"<p><b>Your decision:</b> {your_dec_text}<br>"
        f"<b>Cost of your decision:</b> {format_currency(your_cost)}</p>"
        f"<p><b>Cost-minimizing decision:</b> {opt_dec_text} — would have cost "
        f"{format_currency(opt_cost)}.</p>"
        f"<p>{explanation}</p>"
    )
    render_feedback_card(body, correct=is_optimal)

    next_label = "Continue to next case" if idx == -2 else "Continue to the scored trials"
    if st.button(next_label, type="primary"):
        _advance_after_practice()


# =============================================================================
# Phase 6: Block intro
# =============================================================================

def block_intro_screen() -> None:
    inject_css()
    block = st.session_state.block_intro_for
    seq = _ensure_trial_sequence()
    protocol = next(t["protocol"] for t in seq if t["block"] == block)
    st.title(f"Round {BLOCK_NUMBER[block]} of 3 — 6 loan applications")
    st.markdown(BLOCK_HEADERS[protocol])
    if st.button(f"Begin Round {BLOCK_NUMBER[block]}", type="primary"):
        _set_phase("trial")


# =============================================================================
# Phase 7: Trial (handles all three protocols and both practice + experimental)
# =============================================================================

def trial_screen() -> None:
    inject_css()
    idx = st.session_state.current_trial_index
    trial = _trial_at(idx)
    case = trial["case"]
    protocol = trial["protocol"]
    seq = st.session_state.trial_sequence

    # Sidebar quick-reference
    is_practice = trial["block"] == "practice"
    render_sidebar_reference(protocol, is_practice=is_practice)

    # Sticky trial header
    if is_practice:
        practice_n = idx + 3            # -2 -> 1, -1 -> 2
        render_trial_header(
            protocol,
            is_practice=True,
            practice_n=practice_n,
        )
    else:
        block_num = BLOCK_NUMBER[trial["block"]]
        pos = _block_position(seq, idx, trial["block"])
        render_trial_header(
            protocol,
            block_num=block_num,
            pos=pos,
        )
        render_overall_progress(idx)

    render_case_card(case, participant_id=str(st.session_state.get("participant_id", "")))

    if protocol == "human_first":
        step_key = f"trial_{idx}_step"
        if step_key not in st.session_state:
            st.session_state[step_key] = "step1"
        if st.session_state[step_key] == "step1":
            _render_human_first_step1(idx, trial)
        else:
            _render_human_first_step2(idx, trial)
    else:
        _render_single_step(idx, trial, protocol)


# -----------------------------------------------------------------------------
# Single-step trial (no_ai, ai_first, practice)
# -----------------------------------------------------------------------------

def _render_single_step(idx: int, trial: dict, protocol: str) -> None:
    case = trial["case"]
    load_key = f"trial_{idx}_load_time"
    if load_key not in st.session_state:
        st.session_state[load_key] = now_ms()

    if protocol == "ai_first":
        render_ai_panel(case)

    with st.container(border=True):
        render_response_card_header()

        # Step 1 — Decision
        render_step_label(1, "Decision")
        decision = render_decision_buttons(f"trial_{idx}_decision_final")

        render_step_divider()

        # Step 2 — Probability estimate (disabled until decision is set)
        prob_disabled = decision is None
        render_step_label(2, "Probability of Default", active=not prob_disabled)
        prob = render_probability_slider_mandatory(
            f"trial_{idx}_prob_final",
            "Estimated probability this borrower will default:",
            disabled=prob_disabled,
        )

        render_step_divider()

        # Step 3 — Submit
        render_step_label(3, "Submit", active=not (decision is None or prob is None))
        submitted = submit_button_with_gate(
            state_key=f"trial_{idx}_submit",
            label="Submit Decision",
            decision=decision,
            prob=prob,
            load_time_ms=st.session_state[load_key],
        )

    if submitted:
        end_ms = now_ms()
        elapsed = end_ms - st.session_state[load_key]
        if _save_trial_row(
            idx=idx,
            trial=trial,
            protocol=protocol,
            decision_init=None,
            prob_init=None,
            time_to_init_ms=None,
            decision_final=decision,
            prob_final=prob,
            confidence=None,
            time_to_final_ms=elapsed,
            total_trial_ms=elapsed,
        ):
            _advance_after_trial(was_practice=trial["block"] == "practice")


# -----------------------------------------------------------------------------
# Human-first Step 1
# -----------------------------------------------------------------------------

def _render_human_first_step1(idx: int, trial: dict) -> None:
    load_key = f"trial_{idx}_load_time"
    if load_key not in st.session_state:
        st.session_state[load_key] = now_ms()

    with st.container(border=True):
        render_response_card_header()

        # Step 1 — Decision
        render_step_label(1, "Your Initial Decision")
        decision = render_decision_buttons(f"trial_{idx}_decision_init")

        render_step_divider()

        # Step 2 — Probability (disabled until decision set)
        prob_disabled = decision is None
        render_step_label(2, "Probability of Default", active=not prob_disabled)
        prob = render_probability_slider_mandatory(
            f"trial_{idx}_prob_init",
            "Estimated probability this borrower will default:",
            disabled=prob_disabled,
        )

        render_step_divider()

        # Step 3 — Submit initial
        render_step_label(3, "Submit Initial Assessment", active=not (decision is None or prob is None))
        submitted = submit_button_with_gate(
            state_key=f"trial_{idx}_step1_submit",
            label="Submit Initial Assessment",
            decision=decision,
            prob=prob,
            load_time_ms=st.session_state[load_key],
        )

    if submitted:
        now = now_ms()
        # Persist widget values BEFORE rerun — Streamlit clears widget keys
        # when the widget is no longer rendered (Step 1 slider disappears in Step 2)
        st.session_state[f"trial_{idx}_prob_init_saved"] = st.session_state[f"trial_{idx}_prob_init"]
        st.session_state[f"trial_{idx}_decision_init_saved"] = st.session_state[f"trial_{idx}_decision_init"]
        st.session_state[f"trial_{idx}_step1_submit_time"] = now
        st.session_state[f"trial_{idx}_time_to_init_ms"] = now - st.session_state[load_key]
        st.session_state[f"trial_{idx}_step"] = "step2"
        st.session_state[f"trial_{idx}_step2_load_time"] = now
        st.rerun()


# -----------------------------------------------------------------------------
# Human-first Step 2
# -----------------------------------------------------------------------------

def _render_human_first_step2(idx: int, trial: dict) -> None:
    case = trial["case"]
    decision_init = st.session_state[f"trial_{idx}_decision_init_saved"]
    prob_init_widget = st.session_state[f"trial_{idx}_prob_init_saved"]   # int 0..100
    prob_init_float = float(prob_init_widget) / 100.0
    initial_percent = int(prob_init_widget)

    # Pre-fill Step-2 widgets with Step-1 values on first render of Step 2.
    # We set the widget keys directly here so submit can be enabled immediately;
    # the participant may revise either field before submitting.
    if f"trial_{idx}_decision_final" not in st.session_state:
        st.session_state[f"trial_{idx}_decision_final"] = decision_init

    render_locked_step1_summary(decision_init, prob_init_float)
    render_ai_panel(case)

    with st.container(border=True):
        render_response_card_header()

        # Step 1 — Revise decision (pre-filled from Step 1)
        render_step_label(1, "Revise Your Decision  (optional)")
        decision = render_decision_buttons(f"trial_{idx}_decision_final")

        render_step_divider()

        # Step 2 — Revise probability (pre-filled, always enabled)
        render_step_label(2, "Revise Probability of Default  (optional)")
        prob = render_probability_slider_prefilled(
            f"trial_{idx}_prob_final",
            "Estimated probability this borrower will default:",
            initial_percent,
        )

        render_step_divider()

        # Step 3 — Submit final
        render_step_label(3, "Submit Final Decision", active=True)
        step2_load = st.session_state[f"trial_{idx}_step2_load_time"]
        submitted = submit_button_with_gate(
            state_key=f"trial_{idx}_step2_submit",
            label="Submit Final Decision",
            decision=decision,
            prob=prob,
            load_time_ms=step2_load,
        )

    if submitted:
        end_ms = now_ms()
        time_to_final = end_ms - step2_load
        total_time = end_ms - st.session_state[f"trial_{idx}_load_time"]
        if _save_trial_row(
            idx=idx,
            trial=trial,
            protocol="human_first",
            decision_init=decision_init,
            prob_init=prob_init_float,
            time_to_init_ms=st.session_state[f"trial_{idx}_time_to_init_ms"],
            decision_final=decision,
            prob_final=prob,
            confidence=None,
            time_to_final_ms=time_to_final,
            total_trial_ms=total_time,
        ):
            _advance_after_trial(was_practice=trial["block"] == "practice")


# -----------------------------------------------------------------------------
# Persistence + advance
# -----------------------------------------------------------------------------

def _save_trial_row(
    idx: int,
    trial: dict,
    protocol: str,
    decision_init: int | None,
    prob_init: float | None,
    time_to_init_ms: int | None,
    decision_final: int,
    prob_final: float,
    confidence: int,
    time_to_final_ms: int,
    total_trial_ms: int,
) -> bool:
    """Insert the trial row. Returns True on success. On failure, shows an error
    and returns False — the caller should NOT advance phase."""
    case = trial["case"]
    row = {
        "participant_id": st.session_state.participant_id,
        "trial_index": idx,
        "case_id": case["case_id"],
        "case_position": case["case_position"],
        "block": trial["block"],
        "protocol": protocol,
        "difficulty_tier": case["difficulty_tier"],
        "difficulty_score": case["difficulty_score"],
        "y_true": case["y_true"],
        "pred_prob": case["pred_prob"],
        "model_correct": case["correct"],
        "model_optimal": case["model_optimal"],
        "decision_init": decision_init,
        "prob_estimate_init": prob_init,
        "time_to_init_ms": time_to_init_ms,
        "decision_final": decision_final,
        "prob_estimate_final": prob_final,
        "confidence": confidence,
        "time_to_final_ms": time_to_final_ms,
        "total_trial_ms": total_trial_ms,
    }
    try:
        insert_trial(row)
        return True
    except Exception:
        st.error(
            "We couldn't save your response. Please click **Submit** again. "
            "Your selections are preserved."
        )
        return False


def _advance_after_trial(was_practice: bool) -> None:
    idx = st.session_state.current_trial_index
    if was_practice:
        _set_phase("practice_feedback")
        return
    _advance_to_next(idx)


def _advance_after_practice() -> None:
    idx = st.session_state.current_trial_index
    _advance_to_next(idx)


def _advance_to_next(just_finished_idx: int) -> None:
    """Move to the appropriate next phase after a trial (or its feedback) is done."""
    if just_finished_idx == -2:
        st.session_state.current_trial_index = -1
        _set_phase("trial", trial_index=-1)
    elif just_finished_idx == -1:
        st.session_state.current_trial_index = 1
        st.session_state.block_intro_for = "block_1"
        _set_phase("block_intro", trial_index=1)
    elif just_finished_idx == 6:
        st.session_state.current_trial_index = 7
        st.session_state.block_intro_for = "block_2"
        _set_phase("block_intro", trial_index=7)
    elif just_finished_idx == 12:
        st.session_state.current_trial_index = 13
        st.session_state.block_intro_for = "block_3"
        _set_phase("block_intro", trial_index=13)
    elif just_finished_idx == 18:
        _set_phase("reflection")
    else:
        st.session_state.current_trial_index = just_finished_idx + 1
        _set_phase("trial", trial_index=just_finished_idx + 1)


# =============================================================================
# Phase 8a: Reflection (metacognitive self-report)
# =============================================================================

def reflection_screen() -> None:
    inject_css()
    st.title("Almost done")
    st.markdown(REFLECTION_INTRO)
    st.markdown("---")

    reliance = st.radio(
        RELIANCE_QUESTION,
        options=RELIANCE_OPTIONS,
        index=None,
        key="reflection_reliance_input",
    )

    st.markdown("")  # small spacing

    surprise = st.radio(
        SURPRISE_QUESTION,
        options=SURPRISE_OPTIONS,
        index=None,
        key="reflection_surprise_input",
    )

    ready = (reliance is not None) and (surprise is not None)
    if st.button("Continue", type="primary", disabled=not ready):
        try:
            update_participant_reflection(
                st.session_state.participant_id, reliance, surprise
            )
        except Exception:
            # Non-fatal: reflection is ancillary; trial data is the primary record.
            # Log to session so we can still attempt a retry path if needed.
            pass
        st.session_state.reflection_reliance = reliance
        st.session_state.reflection_surprise = surprise
        _set_phase("trust")


# =============================================================================
# Phase 8b: Trust rating
# =============================================================================

def trust_screen() -> None:
    inject_css()
    st.title("One last question")
    rating = st.radio(
        TRUST_QUESTION,
        options=list(TRUST_LABELS.keys()),
        format_func=lambda x: TRUST_LABELS[x],
        index=None,
        horizontal=True,
        key="trust_rating_input",
    )
    if st.button("Continue", type="primary", disabled=rating is None):
        st.session_state.trust_rating = rating
        _set_phase("performance")


# =============================================================================
# Phase 9: Performance
# =============================================================================

def performance_screen() -> None:
    inject_css()
    st.title("Your performance")

    seq = _ensure_trial_sequence()

    # Read the 18 experimental trials from the database. This is robust to
    # page refreshes and is the canonical record anyway.
    try:
        db_trials = get_participant_trials(st.session_state.participant_id)
    except Exception:
        st.error("We couldn't load your trial data. Please refresh and try again.")
        return
    trials_by_index = {t["trial_index"]: t for t in db_trials}

    experimental_trials = []
    for t in seq:
        if t["block"] == "practice":
            continue
        db_trial = trials_by_index.get(t["trial_index"])
        if not db_trial:
            continue
        experimental_trials.append(
            {
                "decision_final": db_trial["decision_final"],
                "y_true": t["case"]["y_true"],
                "pred_prob": t["case"]["pred_prob"],
            }
        )
    perf = compute_performance(experimental_trials)

    # Persist completion to DB exactly once.
    if not st.session_state.get("performance_saved"):
        try:
            complete_participant(
                st.session_state.participant_id,
                st.session_state.trust_rating,
                perf["total_cost"],
                perf["optimal_cost"],
            )
            st.session_state.performance_saved = True
        except Exception:
            st.error(
                "We couldn't finalize your record. Please refresh; your trial responses are saved."
            )
            return

    tier = performance_tier(perf["total_cost"], perf["optimal_cost"])
    st.markdown(
        f"**Total losses:** {format_currency(perf['total_cost'])}  \n"
        f"**Best possible strategy:** {format_currency(perf['optimal_cost'])}"
    )
    st.markdown("#### Breakdown")
    st.markdown(
        f"- Correct approvals (approved, borrower repaid): **{perf['correct_approvals']}**\n"
        f"- Correct rejections (rejected, borrower would have defaulted): **{perf['correct_rejections']}**\n"
        f"- Costly approvals (approved, borrower defaulted — $5,000 each): **{perf['costly_approvals']}**\n"
        f"- Missed opportunities (rejected, borrower would have repaid — $1,000 each): **{perf['missed_opportunities']}**"
    )
    st.info(PERFORMANCE_MESSAGES[tier])

    if st.button("Continue", type="primary"):
        _set_phase("thank_you")


# =============================================================================
# Phase 10: Thank you
# =============================================================================

def thank_you_screen() -> None:
    inject_css()
    st.title("Thank you")
    st.markdown(THANK_YOU_TEXT)


# =============================================================================
# Terminal: already completed
# =============================================================================

def already_completed_screen() -> None:
    inject_css()
    st.title("Thank you")
    st.markdown(ALREADY_COMPLETED_TEXT)