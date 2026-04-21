"""
Reusable UI building blocks: case card, AI panel, decision buttons,
probability slider (with mandatory-set logic),
submit button (with the 5-second review gate).

Every component takes a `key` prefix so multiple instances on different
trials don't collide in st.session_state.
"""

from __future__ import annotations

import hashlib
from typing import Optional

import streamlit as st

from config import MIN_TRIAL_TIME_MS
from utils import (
    ai_recommendation_label,
    dti_descriptor,
    format_percent,
    home_ownership_verb,
    income_descriptor,
    income_from_log,
    now_ms,
    purpose_display,
    utilization_descriptor,
)


# =============================================================================
# Page-level CSS (called once from app.py)
# =============================================================================

PAGE_CSS = """
<style>
/* Force explicit colors on all custom components so dark mode cannot break them */
.case-card {
    background: #f7f9fb;
    border: 1px solid #d8dde3;
    border-radius: 10px;
    padding: 20px 22px;
    margin: 12px 0 18px 0;
    line-height: 1.6;
    font-size: 1.02rem;
    color: #1a1a2e;
}
.case-card h3 {
    margin-top: 0 !important;
    margin-bottom: 10px;
    font-size: 1.12rem;
    color: #2c3e50;
}
.case-card p {
    color: #1a1a2e;
}
.case-card b {
    color: #0d1b2a;
}
.ai-panel {
    background: #eaf3fb;
    border: 1px solid #9bbfdd;
    border-radius: 10px;
    padding: 18px 22px;
    margin: 6px 0 18px 0;
    line-height: 1.5;
    color: #1a1a2e;
}
.ai-panel .ai-label {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #2a5d8f;
    font-weight: 700;
    margin-bottom: 6px;
}
.ai-panel h4 {
    margin: 0 0 10px 0;
    color: #1d3a5e;
}
.ai-panel p {
    color: #1a1a2e;
}
.locked-step {
    background: #f1f3f5;
    border: 1px dashed #c9ced3;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0 16px 0;
    color: #495057;
    font-size: 0.95rem;
}
.feedback-card {
    border-radius: 10px;
    padding: 18px 22px;
    margin: 14px 0;
    line-height: 1.55;
    color: #1a1a2e;
}
.feedback-correct  { background: #e8f6ec; border: 1px solid #8cc69d; }
.feedback-suboptimal { background: #fdf3e6; border: 1px solid #e1b478; }
.progress-line {
    color: #6c757d;
    font-size: 0.92rem;
    margin-bottom: 4px;
}
/* Overall progress bar */
.progress-bar-container {
    background: #e9ecef;
    border-radius: 6px;
    height: 8px;
    margin: 0 0 16px 0;
    overflow: hidden;
}
.progress-bar-fill {
    height: 100%;
    border-radius: 6px;
    background: linear-gradient(90deg, #4a90d9, #2e6cb5);
    transition: width 0.3s ease;
}
</style>
"""


def inject_css() -> None:
    st.markdown(PAGE_CSS, unsafe_allow_html=True)


# =============================================================================
# Case profile (natural-language prose)
# =============================================================================

def render_case_card(case: dict, participant_id: str = "") -> None:
    """
    Render a loan application as a prose description.

    To reduce monotony across 18 near-identically-structured trials,
    the opening sentence uses one of three equivalent phrasings. The
    variant is chosen deterministically per (participant_id, case_id),
    so a given participant sees the same case with the same wording
    on any reload, but different participants see different phrasings.
    The information content is identical across variants.
    """
    income_dollars = income_from_log(case["log_annual_inc"])
    inc_desc = income_descriptor(income_dollars)
    dti_desc = dti_descriptor(case["dti"])
    util_desc = utilization_descriptor(case["revol_util"])
    home_verb = home_ownership_verb(case["home_ownership"])
    purp = purpose_display(case["purpose"])

    title_position = case["case_position"]
    title = f"Loan Application #{title_position}" if title_position > 0 else "Practice Application"

    # Deterministic template selection per (participant, case).
    # Same participant + same case -> same template on every render.
    seed = hashlib.md5(f"{participant_id}:{case['case_id']}".encode()).hexdigest()
    variant = int(seed, 16) % 3

    loan_amnt = f'<b>${case["loan_amnt"]:,}</b>'
    int_rate = f'<b>{case["int_rate"]:.2f}%</b>'
    term = f'<b>{case["term"]}</b>'
    purp_b = f'<b>{purp}</b>'

    if variant == 0:
        opener = (
            f'<p>The applicant is requesting a {loan_amnt} loan at an interest '
            f'rate of {int_rate}, to be repaid over {term}. The purpose of the '
            f'loan is {purp_b}.</p>'
        )
    elif variant == 1:
        opener = (
            f'<p>A borrower has applied for a {loan_amnt} loan at {int_rate} '
            f'interest, with a {term} repayment term. They intend to use the '
            f'funds for {purp_b}.</p>'
        )
    else:  # variant == 2
        opener = (
            f'<p>This application is for a {loan_amnt} loan, priced at '
            f'{int_rate} and structured over {term}. The stated purpose '
            f'is {purp_b}.</p>'
        )

    html = (
        f'<div class="case-card">'
        f'<h3>{title}</h3>'
        f'{opener}'
        f'<p>The applicant earns approximately <b>${income_dollars:,}</b> per year ({inc_desc}) '
        f'and currently uses <b>{case["dti"]:.1f}%</b> of their monthly income to service '
        f'existing debts ({dti_desc}). They are using <b>{case["revol_util"]:.1f}%</b> of their '
        f'available credit ({util_desc}), and have maintained credit accounts for '
        f'<b>{case["credit_history_years"]:.1f} years</b>. The applicant currently '
        f'<b>{home_verb}</b> their home.</p>'
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


# =============================================================================
# AI assessment panel
# =============================================================================

def render_ai_panel(case: dict) -> None:
    pct = format_percent(case["pred_prob"])
    rec = ai_recommendation_label(case["pred_prob"])
    html = (
        f'<div class="ai-panel">'
        f'<div class="ai-label">AI Risk Assessment</div>'
        f'<h4>The AI estimates a {pct} probability that this borrower will default.</h4>'
        f'<p>Based on the bank\'s risk policy, the AI recommends: <b>{rec}</b>.</p>'
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


# =============================================================================
# Decision buttons (APPROVE / REJECT)
# =============================================================================

def render_decision_buttons(state_key: str) -> Optional[int]:
    """
    Two large buttons; the selected one shows in 'primary' style.
    Returns 1 (approve), 0 (reject), or None.
    The selection is stored in st.session_state[state_key] as 1/0.
    """
    current = st.session_state.get(state_key)
    col1, col2 = st.columns(2)
    with col1:
        approve_clicked = st.button(
            "✓  APPROVE",
            key=f"{state_key}__approve_btn",
            type="primary" if current == 1 else "secondary",
            use_container_width=True,
        )
    with col2:
        reject_clicked = st.button(
            "✗  REJECT",
            key=f"{state_key}__reject_btn",
            type="primary" if current == 0 else "secondary",
            use_container_width=True,
        )
    if approve_clicked:
        st.session_state[state_key] = 1
        st.rerun()
    if reject_clicked:
        st.session_state[state_key] = 0
        st.rerun()
    return st.session_state.get(state_key)


def decision_label(decision: int) -> str:
    return "APPROVE" if decision == 1 else "REJECT"


# =============================================================================
# Probability slider with mandatory-set logic
# =============================================================================

_PROB_NOT_SET = "—"


def render_probability_slider_mandatory(key: str, label: str) -> Optional[float]:
    """
    Select-slider whose first option is a sentinel ('—'). The participant must
    move the slider before the value is considered set. Returns the probability
    as a float in [0, 1], or None if not set.
    """
    if key not in st.session_state:
        st.session_state[key] = _PROB_NOT_SET

    options = [_PROB_NOT_SET] + list(range(0, 101))

    def _format(x):
        return "— Please set —" if x == _PROB_NOT_SET else f"{x}%"

    selected = st.select_slider(label, options=options, format_func=_format, key=key)
    if selected == _PROB_NOT_SET:
        return None
    return float(selected) / 100.0


def render_probability_slider_prefilled(
    key: str, label: str, initial_percent: int
) -> float:
    """
    Regular slider used in human-first Step 2: pre-filled with the participant's
    Step 1 estimate (in percent), editable, always returns a probability in [0, 1].
    """
    if key not in st.session_state:
        st.session_state[key] = initial_percent
    val = st.slider(label, min_value=0, max_value=100, step=1, key=key, format="%d%%")
    return float(val) / 100.0


# =============================================================================
# Confidence slider (optional)
# =============================================================================

# =============================================================================
# Submit button with review-time gate
# =============================================================================

def submit_button_with_gate(
    state_key: str,
    label: str,
    decision: Optional[int],
    prob: Optional[float],
    load_time_ms: int,
) -> bool:
    """
    Renders the submit button, disabled until decision and probability are set.
    On click, if less than MIN_TRIAL_TIME_MS has elapsed since load_time_ms,
    the click is suppressed and a small caption is shown. Returns True when
    a valid submit was registered.
    """
    decision_set = decision is not None
    prob_set = prob is not None
    elapsed = now_ms() - load_time_ms
    time_ok = elapsed >= MIN_TRIAL_TIME_MS

    disabled = not (decision_set and prob_set)
    clicked = st.button(label, type="primary", disabled=disabled, key=f"{state_key}__submit", use_container_width=True)

    if clicked:
        if not time_ok:
            remaining = max(0, (MIN_TRIAL_TIME_MS - elapsed) / 1000.0)
            st.caption(
                f"Please take a moment to review — ready in {remaining:.0f}s."
            )
            return False
        return True

    # Show a subtle indicator when decision and prob are set but the time gate is still active.
    if decision_set and prob_set and not time_ok:
        remaining = max(0, (MIN_TRIAL_TIME_MS - elapsed) / 1000.0)
        st.caption(f"Ready to submit in ~{remaining:.0f}s.")
    return False


# =============================================================================
# Locked step-1 summary (human-first protocol)
# =============================================================================

def render_locked_step1_summary(decision_init: int, prob_init: float) -> None:
    decision_text = decision_label(decision_init)
    pct = format_percent(prob_init)
    html = (
        f'<div class="locked-step">'
        f'<b>Your initial assessment:</b> {decision_text}, with a {pct} estimated '
        f"probability of default."
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


# =============================================================================
# Progress line above each trial
# =============================================================================

def render_progress_line(text: str) -> None:
    st.markdown(f'<div class="progress-line">{text}</div>', unsafe_allow_html=True)


def render_overall_progress(current_trial_index: int) -> None:
    """
    Render a visual progress bar showing how far the participant is through
    the 18 experimental trials. Practice trials (-2, -1) show 0%.
    """
    if current_trial_index < 1:
        completed = 0
    else:
        completed = current_trial_index - 1  # trial 1 = 0 completed, trial 18 = 17 completed
    total = 18
    pct = min(100, int((completed / total) * 100))
    html = (
        f'<div class="progress-bar-container">'
        f'<div class="progress-bar-fill" style="width: {pct}%;"></div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# =============================================================================
# Feedback card (practice trials only)
# =============================================================================

def render_feedback_card(html: str, correct: bool) -> None:
    cls = "feedback-correct" if correct else "feedback-suboptimal"
    st.markdown(f'<div class="feedback-card {cls}">{html}</div>', unsafe_allow_html=True)