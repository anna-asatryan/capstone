"""
Pure helper functions with no Streamlit or Supabase dependencies.
Used by experiment_logic, ui_components, and screens.
"""

import hashlib
import math
import time

from config import C_FN, C_FP, TAU, HOME_OWNERSHIP_VERB, PURPOSE_DISPLAY


# =============================================================================
# Timing
# =============================================================================

def now_ms() -> int:
    """Monotonic-enough millisecond timestamp. time.time() is fine for
    wall-clock durations in this experiment."""
    return int(time.time() * 1000)


# =============================================================================
# Deterministic seeding
# =============================================================================

def stable_seed(participant_id: str, block_name: str) -> int:
    """
    Produces a reproducible 32-bit seed from (participant_id, block_name).

    Python's built-in hash() is randomized per interpreter run, so we use md5
    to get a stable value across processes. This matters if a participant
    resumes a session in a new Streamlit process: the shuffled order of cases
    in each block must match what they saw before the reload.
    """
    h = hashlib.md5(f"{participant_id}:{block_name}".encode("utf-8")).hexdigest()
    return int(h, 16) % (2 ** 32)


# =============================================================================
# Display helpers
# =============================================================================

def income_from_log(log_annual_inc: float) -> int:
    """Convert log-income back to dollars, rounded to nearest thousand for display."""
    raw = math.exp(log_annual_inc)
    return int(round(raw / 1000.0)) * 1000


def income_descriptor(income_dollars: int) -> str:
    if income_dollars < 30000:
        return "low income"
    if income_dollars <= 100000:
        return "medium income"
    return "high income"


def dti_descriptor(dti: float) -> str:
    if dti < 15:
        return "low debt burden"
    if dti <= 30:
        return "moderate debt burden"
    return "high debt burden"


def utilization_descriptor(util: float) -> str:
    if util < 30:
        return "low utilization"
    if util <= 70:
        return "moderate utilization"
    return "high utilization"


def home_ownership_verb(home_ownership: str) -> str:
    return HOME_OWNERSHIP_VERB.get(home_ownership, "lives in")


def purpose_display(purpose: str) -> str:
    return PURPOSE_DISPLAY.get(purpose, purpose.replace("_", " "))


def format_currency(amount: float) -> str:
    return f"${int(round(amount)):,}"


def format_percent(prob: float) -> str:
    """Format a [0,1] probability as an integer percentage string."""
    return f"{int(round(prob * 100))}%"


# =============================================================================
# Decision / cost helpers
# =============================================================================

def ai_recommendation(pred_prob: float) -> int:
    """1 = APPROVE, 0 = REJECT. Threshold TAU = C_FP / (C_FP + C_FN) = 0.1667."""
    return 1 if pred_prob < TAU else 0


def ai_recommendation_label(pred_prob: float) -> str:
    return "APPROVE" if ai_recommendation(pred_prob) == 1 else "REJECT"


def optimal_decision(pred_prob: float) -> int:
    """Same rule as ai_recommendation, but named for clarity when computing optimal cost."""
    return ai_recommendation(pred_prob)


def trial_cost(decision: int, y_true: int) -> int:
    """
    Realized dollar cost of a single decision.

    decision = 1 (approve), y_true = 1 (default) -> C_FN loss
    decision = 0 (reject),  y_true = 0 (repaid)  -> C_FP loss
    otherwise -> 0
    """
    if decision == 1 and y_true == 1:
        return C_FN
    if decision == 0 and y_true == 0:
        return C_FP
    return 0


def performance_tier(total_cost: float, optimal_cost: float) -> str:
    """Classify participant performance for the end-of-experiment message."""
    gap = max(0.0, total_cost - optimal_cost)
    if gap <= 3000:
        return "excellent"
    if gap <= 8000:
        return "good"
    if gap <= 15000:
        return "fair"
    return "low"
