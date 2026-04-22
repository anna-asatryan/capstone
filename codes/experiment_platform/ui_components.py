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
# Page-level CSS (called once from inject_css())
# =============================================================================

PAGE_CSS = """
<style>
/* ─── Typography baseline ─────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* ─── Case card ────────────────────────────────────────────────────────────── */
.case-card {
    background: #f7f9fb;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    padding: 22px 26px;
    margin: 14px 0 20px 0;
    line-height: 1.65;
    font-size: 1.05rem;
    color: #1a1a2e;
}
.case-card h3 {
    margin-top: 0 !important;
    margin-bottom: 12px;
    font-size: 1.0rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    color: #2c3e50;
    text-transform: uppercase;
    border-bottom: 1px solid #d0d7de;
    padding-bottom: 8px;
}
.case-card p {
    color: #1a1a2e;
    margin-bottom: 0.5em;
}
.case-card b {
    color: #0d1b2a;
}

/* ─── AI assessment panel ──────────────────────────────────────────────────── */
.ai-panel {
    background: #eaf3fb;
    border: 1px solid #9bbfdd;
    border-radius: 8px;
    padding: 18px 24px;
    margin: 8px 0 20px 0;
    line-height: 1.55;
    color: #1a1a2e;
}
.ai-panel .ai-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #2a5d8f;
    font-weight: 700;
    margin-bottom: 6px;
}
.ai-panel h4 {
    margin: 0 0 8px 0;
    font-size: 1.05rem;
    color: #1d3a5e;
}
.ai-panel p {
    color: #1a1a2e;
    margin: 0;
}

/* ─── Locked step-1 summary (human-first protocol) ─────────────────────────── */
.locked-step {
    background: #f1f3f5;
    border: 1px dashed #c2c8cf;
    border-radius: 7px;
    padding: 12px 18px;
    margin: 10px 0 18px 0;
    color: #495057;
    font-size: 0.97rem;
}

/* ─── Feedback card ─────────────────────────────────────────────────────────── */
.feedback-card {
    border-radius: 8px;
    padding: 20px 24px;
    margin: 16px 0;
    line-height: 1.6;
    color: #1a1a2e;
    font-size: 1.02rem;
}
.feedback-correct   { background: #e8f6ec; border: 1px solid #82c49a; }
.feedback-suboptimal { background: #fdf3e6; border: 1px solid #dba96a; }

/* ─── Progress indicators ──────────────────────────────────────────────────── */
.progress-line {
    color: #6c757d;
    font-size: 0.9rem;
    margin-bottom: 4px;
    letter-spacing: 0.01em;
}
.progress-bar-container {
    background: #e4e8ed;
    border-radius: 6px;
    height: 6px;
    margin: 2px 0 18px 0;
    overflow: hidden;
}
.progress-bar-fill {
    height: 100%;
    border-radius: 6px;
    background: linear-gradient(90deg, #4a90d9, #2e6cb5);
    transition: width 0.4s ease;
}

/* ─── Trial header ──────────────────────────────────────────────────────────── */
.trial-header {
    position: sticky;
    top: 0;
    z-index: 100;
    background: #ffffff;
    border-bottom: 1px solid #d0d7de;
    padding: 10px 0 10px 0;
    margin: 0 0 18px 0;
}
.trial-header-inner {
    display: flex;
    align-items: baseline;
    gap: 14px;
    flex-wrap: wrap;
}
.trial-header-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: #1a1a2e;
    letter-spacing: 0.01em;
    white-space: nowrap;
}
.trial-header-meta {
    font-size: 0.88rem;
    color: #6c757d;
    white-space: nowrap;
}
.trial-header-badge {
    display: inline-block;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 2px 9px;
    border-radius: 4px;
    margin-left: 4px;
}
.badge-noai     { background: #eef0f2; color: #495057; border: 1px solid #c6ccd2; }
.badge-aifirst  { background: #e5f0fb; color: #1d3a5e; border: 1px solid #9bbfdd; }
.badge-humanfirst { background: #fef6e8; color: #6b4e12; border: 1px solid #e3c07a; }
.badge-practice { background: #f0f0f0; color: #555; border: 1px solid #ccc; }

/* ─── Response module card ──────────────────────────────────────────────────── */
.response-card-header {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: #6c757d;
    padding: 0 0 10px 0;
    border-bottom: 1px solid #d0d7de;
    margin-bottom: 16px;
}

/* ─── Step labels ────────────────────────────────────────────────────────────── */
.step-label {
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #6c757d;
    margin: 18px 0 6px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.step-label .step-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #2e6cb5;
    color: #fff;
    font-size: 0.68rem;
    font-weight: 700;
    flex-shrink: 0;
}
.step-label .step-num.inactive {
    background: #c2c8cf;
}
.step-label .step-text {
    color: #2c3e50;
}
.step-label .step-text.inactive {
    color: #9aa4ae;
}
.step-divider {
    border: none;
    border-top: 1px solid #e9ecef;
    margin: 16px 0;
}

/* ─── Sidebar quick-reference ───────────────────────────────────────────────── */
.sidebar-section-title {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #6c757d;
    margin: 16px 0 6px 0;
    padding-bottom: 4px;
    border-bottom: 1px solid #d0d7de;
}
.sidebar-term {
    font-size: 0.88rem;
    margin: 6px 0 2px 0;
    color: #1a1a2e;
}
.sidebar-term b {
    color: #0d1b2a;
}
.sidebar-rule {
    font-size: 0.87rem;
    color: #2c3e50;
    margin: 4px 0;
    padding-left: 4px;
}
.sidebar-cost-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
    padding: 3px 0;
    color: #1a1a2e;
}
.sidebar-cost-loss {
    color: #c0392b;
    font-weight: 600;
}
</style>
"""


def inject_css() -> None:
    st.markdown(PAGE_CSS, unsafe_allow_html=True)


# =============================================================================
# Protocol display helpers
# =============================================================================

_PROTOCOL_LABEL = {
    "no_ai":       "Independent Review",
    "ai_first":    "AI-Assisted Review",
    "human_first": "Sequential Review",
    "practice":    "Practice",
}

_PROTOCOL_BADGE_CLASS = {
    "no_ai":       "badge-noai",
    "ai_first":    "badge-aifirst",
    "human_first": "badge-humanfirst",
    "practice":    "badge-practice",
}


def _protocol_label(protocol: str) -> str:
    return _PROTOCOL_LABEL.get(protocol, protocol)


def _protocol_badge_class(protocol: str) -> str:
    return _PROTOCOL_BADGE_CLASS.get(protocol, "badge-noai")


# =============================================================================
# Trial header (sticky context bar)
# =============================================================================

def render_trial_header(
    protocol: str,
    *,
    block_num: int | None = None,
    pos: int | None = None,
    is_practice: bool = False,
    practice_n: int | None = None,
) -> None:
    """
    Renders a sticky header bar showing the study title, protocol badge,
    and current position. Appears at the very top of each trial screen.
    """
    label = _protocol_label(protocol)
    badge_cls = _protocol_badge_class(protocol)

    if is_practice:
        meta = f"Practice Trial {practice_n} of 2"
        badge_cls = "badge-practice"
        label = "Practice"
    else:
        meta = f"Round {block_num} of 3 &nbsp;·&nbsp; Application {pos} of 6"

    html = (
        f'<div class="trial-header">'
        f'  <div class="trial-header-inner">'
        f'    <span class="trial-header-title">Loan Decision Study</span>'
        f'    <span class="trial-header-badge {badge_cls}">{label}</span>'
        f'    <span class="trial-header-meta">{meta}</span>'
        f'  </div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# =============================================================================
# Sidebar quick-reference
# =============================================================================

def render_sidebar_reference(protocol: str, is_practice: bool = False) -> None:
    """
    Renders a compact participant quick-reference panel in the sidebar.
    Shown during all trial screens.
    """
    label = _protocol_label(protocol) if not is_practice else "Practice"

    with st.sidebar:
        st.markdown(
            f'<div class="sidebar-section-title">Current Mode</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p class="sidebar-rule">'
            f'<span class="trial-header-badge {_protocol_badge_class(protocol)}">'
            f'{label}</span></p>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="sidebar-section-title">Task Sequence</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="sidebar-rule">① Select <b>Approve</b> or <b>Reject</b></p>'
            '<p class="sidebar-rule">② Estimate default probability</p>'
            '<p class="sidebar-rule">③ Submit your decision</p>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="sidebar-section-title">Decision Cost</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="sidebar-cost-row"><span>Approve → borrower defaults</span>'
            '<span class="sidebar-cost-loss">$5,000</span></div>'
            '<div class="sidebar-cost-row"><span>Reject → would have repaid</span>'
            '<span class="sidebar-cost-loss">$1,000</span></div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="sidebar-section-title">Key Terms</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="sidebar-term"><b>Default</b> — borrower fails to repay</p>'
            '<p class="sidebar-term"><b>Term</b> — repayment period (36/60 mos)</p>'
            '<p class="sidebar-term"><b>Interest rate</b> — annual % paid on loan</p>'
            '<p class="sidebar-term"><b>DTI</b> — % of income used for debt payments</p>'
            '<p class="sidebar-term"><b>Revol. utilization</b> — % of credit limit in use</p>'
            '<p class="sidebar-term"><b>Credit history</b> — years of credit accounts</p>',
            unsafe_allow_html=True,
        )

        if protocol == "ai_first":
            st.markdown(
                '<div class="sidebar-section-title">AI Prediction</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p class="sidebar-rule">AI estimate shown <b>before</b> your decision. '
                'You may agree or disagree.</p>',
                unsafe_allow_html=True,
            )
        elif protocol == "human_first":
            st.markdown(
                '<div class="sidebar-section-title">AI Prediction</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p class="sidebar-rule">Decide first, then see AI estimate. '
                'You may revise after.</p>',
                unsafe_allow_html=True,
            )
        elif protocol == "no_ai":
            st.markdown(
                '<div class="sidebar-section-title">This Round</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<p class="sidebar-rule">No AI assistance in this round. '
                'Use your own judgment.</p>',
                unsafe_allow_html=True,
            )


# =============================================================================
# Step label renderer
# =============================================================================

def render_step_label(number: int, text: str, active: bool = True) -> None:
    """Renders a numbered step label above a response widget."""
    num_cls = "step-num" if active else "step-num inactive"
    txt_cls = "step-text" if active else "step-text inactive"
    html = (
        f'<div class="step-label">'
        f'  <span class="{num_cls}">{number}</span>'
        f'  <span class="{txt_cls}">{text}</span>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_response_card_header() -> None:
    """Renders the 'Your Response' header above the response module."""
    st.markdown(
        '<div class="response-card-header">Your Response</div>',
        unsafe_allow_html=True,
    )


def render_step_divider() -> None:
    st.markdown('<hr class="step-divider">', unsafe_allow_html=True)


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
            "✓  Approve",
            key=f"{state_key}__approve_btn",
            type="primary" if current == 1 else "secondary",
            use_container_width=True,
        )
    with col2:
        reject_clicked = st.button(
            "✗  Reject",
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
    return "Approve" if decision == 1 else "Reject"


# =============================================================================
# Probability slider with mandatory-set logic
# =============================================================================

_PROB_NOT_SET = "—"


def render_probability_slider_mandatory(
    key: str,
    label: str,
    disabled: bool = False,
) -> Optional[float]:
    """
    Select-slider whose first option is a sentinel ('—'). The participant must
    move the slider before the value is considered set. Returns the probability
    as a float in [0, 1], or None if not set.

    When `disabled=True` (no decision has been made yet), the slider is
    rendered but non-interactive, with a helper hint beneath it.
    """
    if key not in st.session_state:
        st.session_state[key] = _PROB_NOT_SET

    options = [_PROB_NOT_SET] + list(range(0, 101))

    def _format(x):
        return "— Select above first —" if x == _PROB_NOT_SET else f"{x}%"

    selected = st.select_slider(
        label,
        options=options,
        format_func=_format,
        key=key,
        disabled=disabled,
    )
    if disabled:
        st.caption("Select Approve or Reject above to enable this field.")
        return None
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
    clicked = st.button(
        label,
        type="primary",
        disabled=disabled,
        key=f"{state_key}__submit",
        use_container_width=True,
    )

    if clicked:
        if not time_ok:
            remaining = max(0, (MIN_TRIAL_TIME_MS - elapsed) / 1000.0)
            st.caption(
                f"Please take a moment to review the application — ready in {remaining:.0f}s."
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
        f'<b>Your initial assessment:</b> {decision_text}, '
        f'with a {pct} estimated probability of default.'
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