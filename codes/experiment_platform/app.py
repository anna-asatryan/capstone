"""
Streamlit entry point. The only responsibility of this file is:
  1. Page config + global CSS
  2. Establish a session_id (query param + session_state)
  3. Resume an existing participant if the session_id matches one in Supabase
  4. Route to the screen function for the current phase

All UI lives in screens.py; all DB work in database.py.
"""

from __future__ import annotations

import uuid

import streamlit as st

from config import EXPERIMENT_TITLE
from database import get_participant_by_session
from experiment_logic import build_trial_sequence
from screens import (
    already_completed_screen,
    block_intro_screen,
    consent_screen,
    demographics_screen,
    glossary_screen,
    performance_screen,
    practice_feedback_screen,
    practice_intro_screen,
    quiz_failed_screen,
    quiz_retry_screen,
    quiz_screen,
    reflection_screen,
    thank_you_screen,
    trial_screen,
    trust_screen,
)


PHASE_ROUTER = {
    "consent":             consent_screen,
    "demographics":        demographics_screen,
    "glossary":            glossary_screen,
    "quiz":                quiz_screen,
    "quiz_retry":          quiz_retry_screen,
    "quiz_failed":         quiz_failed_screen,
    "practice_intro":      practice_intro_screen,
    "trial":               trial_screen,
    "practice_feedback":   practice_feedback_screen,
    "block_intro":         block_intro_screen,
    "reflection":          reflection_screen,
    "trust":               trust_screen,
    "performance":         performance_screen,
    "thank_you":           thank_you_screen,
    "already_completed":   already_completed_screen,
}

_BLOCK_OF_INDEX = {
    -2: "practice", -1: "practice",
    1: "block_1", 2: "block_1", 3: "block_1", 4: "block_1", 5: "block_1", 6: "block_1",
    7: "block_2", 8: "block_2", 9: "block_2", 10: "block_2", 11: "block_2", 12: "block_2",
    13: "block_3", 14: "block_3", 15: "block_3", 16: "block_3", 17: "block_3", 18: "block_3",
}


# =============================================================================
# Session bootstrap
# =============================================================================

def _ensure_session_id() -> str:
    """Return the current session_id, creating one in the URL if needed."""
    qp = st.query_params
    sid = st.session_state.get("session_id") or qp.get("s")
    if not sid:
        sid = str(uuid.uuid4())
        qp["s"] = sid
    st.session_state.session_id = sid
    return sid


def _resume_or_start(sid: str) -> None:
    """
    Look up the participant by session_id. If we find a completed one, route to
    'already_completed'. If incomplete, restore participant_id, group, phase,
    and current trial index. Otherwise stay on the consent screen.
    """
    if "phase" in st.session_state:
        # Already initialized in this Streamlit session — nothing to do.
        return

    try:
        participant = get_participant_by_session(sid)
    except Exception:
        participant = None  # treat DB problems as fresh session; user can retry

    if not participant:
        st.session_state.phase = "consent"
        return

    if participant.get("completed"):
        st.session_state.phase = "already_completed"
        return

    # Resume in-flight session
    st.session_state.participant_id = participant["id"]
    st.session_state.participant_number = participant["participant_number"]
    st.session_state.participant_group = participant["participant_group"]
    st.session_state.current_trial_index = participant.get("current_trial_index") or 0
    st.session_state.phase = participant.get("current_phase") or "consent"

    # Rebuild the (deterministic) trial sequence so trial_screen has it.
    st.session_state.trial_sequence = build_trial_sequence(
        participant["id"], participant["participant_group"]
    )

    # If we land on block_intro, restore which block we're introducing.
    if st.session_state.phase == "block_intro":
        st.session_state.block_intro_for = _BLOCK_OF_INDEX.get(
            st.session_state.current_trial_index, "block_1"
        )


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    st.set_page_config(
        page_title=EXPERIMENT_TITLE,
        page_icon="🏦",
        layout="centered",
        initial_sidebar_state="expanded",
    )

    sid = _ensure_session_id()
    _resume_or_start(sid)

    phase = st.session_state.get("phase", "consent")

    # On non-trial screens, render a minimal sidebar so participants know
    # the reference panel will appear during the scored trials.
    if phase not in ("trial", "practice_feedback"):
        with st.sidebar:
            st.markdown(
                "**Loan Decision Study**",
            )
            st.caption(
                "A quick-reference panel will appear here during the scored trials."
            )

    screen = PHASE_ROUTER.get(phase, consent_screen)
    screen()


if __name__ == "__main__":
    main()
