"""
All Supabase operations. No other module should call the Supabase client
directly. Every function retries once on transient error and then raises,
so callers can surface a user-friendly retry message.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import streamlit as st
from supabase import Client, create_client


# =============================================================================
# Client
# =============================================================================

@st.cache_resource(show_spinner=False)
def get_client() -> Client:
    """Cached Supabase client. Cached across reruns and across users
    (the client itself is not participant state)."""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["anon_key"]
    except Exception as exc:
        raise RuntimeError(
            "Supabase credentials are not configured. Copy "
            ".streamlit/secrets.toml.template to .streamlit/secrets.toml and fill it in."
        ) from exc
    return create_client(url, key)


# =============================================================================
# Retry wrapper
# =============================================================================

def _with_retry(fn, *args, **kwargs):
    """
    Run fn once. On any exception, wait 2s and try exactly one more time.
    After the second failure, re-raise so the caller can show an error UI.
    """
    try:
        return fn(*args, **kwargs)
    except Exception:
        time.sleep(2)
        return fn(*args, **kwargs)


# =============================================================================
# Participants
# =============================================================================

def create_participant(session_id: str) -> dict[str, Any]:
    """
    Insert a new participant row. participant_number is assigned by the
    SERIAL column on the server. We then compute participant_group from
    that number and update the row (round-robin).

    Returns the full participant row including id, participant_number, and
    participant_group.
    """
    client = get_client()

    def _insert():
        # insert with a placeholder group; the real group is set once
        # we know the participant_number.
        res = (
            client.table("participants")
            .insert({"session_id": session_id, "participant_group": "group_1"})
            .execute()
        )
        if not res.data:
            raise RuntimeError("No data returned from participant insert.")
        return res.data[0]

    row = _with_retry(_insert)

    # Round-robin by participant_number
    number = row["participant_number"]
    group = ["group_1", "group_2", "group_3"][(number - 1) % 3]

    def _set_group():
        res = (
            client.table("participants")
            .update({"participant_group": group})
            .eq("id", row["id"])
            .execute()
        )
        if not res.data:
            raise RuntimeError("No data returned from participant group update.")
        return res.data[0]

    row = _with_retry(_set_group)
    return row


def update_participant_demographics(
    participant_id: str, age_range: str, education: str
) -> None:
    client = get_client()

    def _update():
        client.table("participants").update(
            {"age_range": age_range, "education": education}
        ).eq("id", participant_id).execute()

    _with_retry(_update)


def update_participant_phase(
    participant_id: str, phase: str, trial_index: int | None = None
) -> None:
    client = get_client()
    payload: dict[str, Any] = {"current_phase": phase}
    if trial_index is not None:
        payload["current_trial_index"] = trial_index

    def _update():
        client.table("participants").update(payload).eq("id", participant_id).execute()

    _with_retry(_update)


def update_participant_reflection(
    participant_id: str,
    self_reported_reliance: str,
    ai_surprise_strategy: str,
) -> None:
    """Store the two metacognitive self-report answers collected just before
    the trust rating. These are used to compare self-reported reliance
    strategy with actual behavioral reliance patterns computed from trials."""
    client = get_client()

    def _update():
        client.table("participants").update(
            {
                "self_reported_reliance": self_reported_reliance,
                "ai_surprise_strategy": ai_surprise_strategy,
            }
        ).eq("id", participant_id).execute()

    _with_retry(_update)


def complete_participant(
    participant_id: str,
    trust_rating: int,
    total_cost: float,
    optimal_cost: float,
) -> None:
    client = get_client()

    def _update():
        client.table("participants").update(
            {
                "trust_rating": trust_rating,
                "total_cost": total_cost,
                "optimal_cost": optimal_cost,
                "completed": True,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "current_phase": "thank_you",
            }
        ).eq("id", participant_id).execute()

    _with_retry(_update)


def get_participant_by_session(session_id: str) -> dict[str, Any] | None:
    """
    Return the most recent participant row matching session_id, or None.
    Most recent is used because a user could reload and retake if their
    previous attempt was incomplete; we want to resume their latest.
    """
    client = get_client()

    def _select():
        res = (
            client.table("participants")
            .select("*")
            .eq("session_id", session_id)
            .order("started_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    return _with_retry(_select)


# =============================================================================
# Trials
# =============================================================================

def insert_trial(trial_row: dict[str, Any]) -> None:
    """
    Insert a trial. Relies on the UNIQUE (participant_id, trial_index) constraint
    to reject duplicates. Upsert by that constraint so a retry never fails and
    never creates a phantom second trial.
    """
    client = get_client()

    def _upsert():
        client.table("trials").upsert(
            trial_row, on_conflict="participant_id,trial_index"
        ).execute()

    _with_retry(_upsert)


def get_participant_trials(participant_id: str) -> list[dict[str, Any]]:
    """Return all trials for a participant, ordered by trial_index."""
    client = get_client()

    def _select():
        res = (
            client.table("trials")
            .select("*")
            .eq("participant_id", participant_id)
            .order("trial_index")
            .execute()
        )
        return res.data or []

    return _with_retry(_select)


# =============================================================================
# Quiz responses
# =============================================================================

def insert_quiz_response(
    participant_id: str,
    attempt: int,
    question_id: int,
    selected_answer: str,
    is_correct: bool,
) -> None:
    client = get_client()

    def _insert():
        client.table("quiz_responses").insert(
            {
                "participant_id": participant_id,
                "attempt": attempt,
                "question_id": question_id,
                "selected_answer": selected_answer,
                "is_correct": is_correct,
            }
        ).execute()

    _with_retry(_insert)
