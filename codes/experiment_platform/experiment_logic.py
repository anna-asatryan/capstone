"""
Trial sequencing, group assignment, randomization, scoring.

Pure functions over the config data and DB rows — no Streamlit here.
"""

from __future__ import annotations

import random
from typing import Any

from config import (
    EXPERIMENTAL_CASES,
    PRACTICE_CASES,
    PRACTICE_PROTOCOL,
    PROTOCOL_ROTATION,
)
from utils import (
    optimal_decision,
    stable_seed,
    trial_cost,
)

BLOCK_NAMES = ["block_1", "block_2", "block_3"]


# =============================================================================
# Group assignment
# =============================================================================

def assign_group(participant_number: int) -> str:
    """Round-robin assignment based on participant_number (SERIAL from DB)."""
    return ["group_1", "group_2", "group_3"][(participant_number - 1) % 3]


def protocol_for(group: str, block: str) -> str:
    return PROTOCOL_ROTATION[group][block]


# =============================================================================
# Within-block randomization
# =============================================================================

def randomize_block_cases(
    participant_id: str, cases: list[dict[str, Any]], block_name: str
) -> list[dict[str, Any]]:
    """
    Shuffle the 6 cases within a block deterministically for this participant.
    The shuffle order is reproducible so that a session can resume mid-block.
    """
    rng = random.Random(stable_seed(participant_id, block_name))
    out = list(cases)
    rng.shuffle(out)
    return out


# =============================================================================
# Trial sequence
# =============================================================================

def build_trial_sequence(participant_id: str, group: str) -> list[dict[str, Any]]:
    """
    Returns the full trial schedule for this participant.

    Each entry is a dict with keys: trial_index, case, protocol, block.
    Practice trials are at trial_index -2 and -1. Experimental trials are 1..18.
    """
    sequence: list[dict[str, Any]] = []

    # Practice (trial_index -2, -1)
    for i, case in enumerate(PRACTICE_CASES):
        sequence.append(
            {
                "trial_index": -2 + i,
                "case": case,
                "protocol": PRACTICE_PROTOCOL,
                "block": "practice",
            }
        )

    # Experimental blocks in fixed block order; within each block, randomized
    cases_by_block: dict[str, list[dict[str, Any]]] = {b: [] for b in BLOCK_NAMES}
    for case in EXPERIMENTAL_CASES:
        cases_by_block[case["block"]].append(case)

    running_index = 1
    for block_name in BLOCK_NAMES:
        protocol = protocol_for(group, block_name)
        shuffled = randomize_block_cases(
            participant_id, cases_by_block[block_name], block_name
        )
        for case in shuffled:
            sequence.append(
                {
                    "trial_index": running_index,
                    "case": case,
                    "protocol": protocol,
                    "block": block_name,
                }
            )
            running_index += 1

    return sequence


def build_demo_trial_sequence() -> list[dict[str, Any]]:
    """Returns exactly 3 trials for the demo mode using curated cases."""
    if len(EXPERIMENTAL_CASES) >= 13:
        cases = [EXPERIMENTAL_CASES[0], EXPERIMENTAL_CASES[6], EXPERIMENTAL_CASES[12]]
    else:
        cases = EXPERIMENTAL_CASES[:3]
        
    sequence = [
        {
            "trial_index": 1,
            "case": cases[0],
            "protocol": "no_ai",
            "block": "demo",
        },
        {
            "trial_index": 2,
            "case": cases[1],
            "protocol": "ai_first",
            "block": "demo",
        },
        {
            "trial_index": 3,
            "case": cases[2],
            "protocol": "human_first",
            "block": "demo",
        }
    ]
    return sequence


# =============================================================================
# Scoring
# =============================================================================

def compute_performance(experimental_trials: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute the post-experiment performance summary from the 18 experimental trials.

    Each trial dict is expected to have decision_final, y_true, and the original
    case's pred_prob (so we can compute the optimal cost).
    """
    total_cost = 0
    correct_approvals = 0   # approved & repaid
    correct_rejections = 0  # rejected & would have defaulted
    costly_approvals = 0    # approved & defaulted ($5,000)
    missed_opportunities = 0  # rejected & would have repaid ($1,000)

    optimal_cost = 0

    for t in experimental_trials:
        decision = t["decision_final"]
        y = t["y_true"]
        total_cost += trial_cost(decision, y)

        if decision == 1 and y == 0:
            correct_approvals += 1
        elif decision == 0 and y == 1:
            correct_rejections += 1
        elif decision == 1 and y == 1:
            costly_approvals += 1
        elif decision == 0 and y == 0:
            missed_opportunities += 1

        optimal_cost += trial_cost(optimal_decision(t["pred_prob"]), y)

    return {
        "total_cost": total_cost,
        "optimal_cost": optimal_cost,
        "correct_approvals": correct_approvals,
        "correct_rejections": correct_rejections,
        "costly_approvals": costly_approvals,
        "missed_opportunities": missed_opportunities,
    }


# =============================================================================
# Quiz
# =============================================================================

def quiz_score(responses: dict[int, str], questions: list[dict[str, Any]]) -> int:
    """responses: question_id -> selected answer letter. Returns count correct."""
    correct = 0
    for q in questions:
        if responses.get(q["id"]) == q["correct"]:
            correct += 1
    return correct
