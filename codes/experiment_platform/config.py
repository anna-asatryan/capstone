"""
Experiment-wide constants: cost parameters, case data, protocol rotation,
all user-facing text, quiz questions, and display mappings.

Edit this file to change wording, case data, quiz content, or experiment
parameters. No other module should hold user-facing strings.
"""

from pathlib import Path

import pandas as pd

_FROZEN_DIR = Path(__file__).resolve().parent / "data" / "frozen"

# =============================================================================
# EXPERIMENT PARAMETERS
# =============================================================================

EXPERIMENT_TITLE = "Loan Decision Study"

C_FN = 5000                                  # cost of approving a defaulter ($)
C_FP = 1000                                  # cost of rejecting a good borrower ($)
TAU = C_FP / (C_FP + C_FN)                   # cost-sensitive decision threshold = 0.1667
MIN_TRIAL_TIME_MS = 3000                     # minimum time before submit enabled (ms)

AGE_RANGES = ["18-24", "25-34", "35-44", "45-54", "55+"]
EDUCATION_LEVELS = [
    "High school",
    "Bachelor's (in progress)",
    "Bachelor's (completed)",
    "Master's or higher",
]

# =============================================================================
# CASE DATA  (loaded from artifacts/frozen/ — do not edit by hand)
# =============================================================================

_CASE_COLUMNS = [
    "case_id", "case_position", "block", "loan_amnt", "term", "int_rate",
    "log_annual_inc", "dti", "revol_util", "home_ownership", "purpose",
    "credit_history_years", "pred_prob", "y_true", "difficulty_tier",
    "difficulty_score", "correct", "model_optimal",
]
_INT_FIELDS = {"case_id", "case_position", "loan_amnt", "y_true", "correct", "model_optimal"}
_STR_FIELDS = {"term", "home_ownership", "purpose", "difficulty_tier", "block"}


def _row_to_dict(row: "pd.Series") -> dict:
    d = {}
    for col in _CASE_COLUMNS:
        val = row[col]
        if col in _INT_FIELDS:
            d[col] = int(val)
        elif col in _STR_FIELDS:
            d[col] = str(val)
        else:
            d[col] = round(float(val), 6)
    return d


_fc = pd.read_csv(_FROZEN_DIR / "final_cases.csv")
EXPERIMENTAL_CASES = [_row_to_dict(row) for _, row in _fc[_CASE_COLUMNS].iterrows()]

_pc = pd.read_csv(_FROZEN_DIR / "practice_cases.csv")
PRACTICE_CASES = [_row_to_dict(row) for _, row in _pc[_CASE_COLUMNS].iterrows()]

# =============================================================================
# PROTOCOL ROTATION (Latin Square — loaded from artifacts/frozen/)
# =============================================================================

_pr = pd.read_csv(_FROZEN_DIR / "protocol_rotation.csv")
PROTOCOL_ROTATION = {
    row["participant_group"]: {
        "block_1": row["block_1_protocol"],
        "block_2": row["block_2_protocol"],
        "block_3": row["block_3_protocol"],
    }
    for _, row in _pr.iterrows()
}

PRACTICE_PROTOCOL = "ai_first"               # practice always uses ai_first — simplest flow + exposes AI panel

# =============================================================================
# DISPLAY MAPPINGS
# =============================================================================

HOME_OWNERSHIP_VERB = {
    "RENT": "rents",
    "OWN": "owns",
    "MORTGAGE": "has a mortgage on",
}

PURPOSE_DISPLAY = {
    "debt_consolidation": "debt consolidation",
    "credit_card": "credit card refinancing",
    "home_improvement": "home improvement",
    "small_business": "a small business",
    "moving": "moving expenses",
    "major_purchase": "a major purchase",
    "medical": "medical expenses",
    "car": "a car purchase",
    "vacation": "a vacation",
    "house": "home-related expenses",
    "other": "other expenses",
}

# =============================================================================
# USER-FACING TEXT
# =============================================================================

CONSENT_TEXT = """
You are invited to participate in a research study on decision-making with AI assistance.
You will review loan applications and decide whether to approve or reject each one. Some
decisions will include AI predictions to assist you. The study takes approximately
**~15 minutes**. No personally identifiable information is collected. Your responses
are anonymous and used for academic research only. You may stop at any time.
"""

DEMOGRAPHICS_INTRO = (
    "Before we begin, please tell us a little about yourself. These two fields are "
    "required for the study, but no personally identifiable information will be collected."
)

GLOSSARY_TEXT = """
**Loan default:** When a borrower fails to repay their loan. This is the outcome you are trying to predict.

**Interest rate:** The annual percentage the borrower pays on top of the loan amount. Higher rates often indicate higher risk.

**Annual income:** The borrower's yearly earnings before taxes.

**Debt-to-income ratio (DTI):** The percentage of the borrower's monthly income that goes toward paying debts. A DTI of 20 means 20% of their income is used for debt payments. Higher values indicate more financial strain.

**Revolving utilization:** How much of their available credit (like credit cards) the borrower is currently using. A utilization of 80% means they are using 80% of their credit limit. Higher values suggest heavier reliance on credit.

**Credit history:** How many years the borrower has had credit accounts. Longer histories generally indicate more financial experience.

**Home ownership:** Whether the borrower rents, owns their home, or has a mortgage. Mortgage holders have demonstrated ability to manage large financial obligations.

**Loan purpose:** Why the borrower wants the money (e.g., debt consolidation, credit card refinancing, home improvement, small business).

**Term:** The repayment period — either 36 months (3 years) or 60 months (5 years). Longer terms mean smaller monthly payments but more total interest.
"""

INSTRUCTIONS_TEXT = """
### Your Role

You are acting as a loan officer at a bank. For each application, you will decide whether to **approve** or **reject** the loan, and estimate the probability that the borrower will default.

### Cost Structure

The bank evaluates your decisions using a simplified cost model:
- Approving a loan that **defaults** costs **$5,000**
- Rejecting a loan that **would have been repaid** costs **$1,000**

The key insight: approving a bad loan is **5 times more costly** than rejecting a good one.

### Three Types of Rounds

You will complete 3 rounds of 6 loan decisions each. The rounds differ in how much help you receive:
- In some rounds, you decide **entirely on your own**
- In some rounds, you see an **AI prediction before** you decide
- In some rounds, you decide first, then **see the AI prediction and can revise**

### What You Provide

For each loan, you will:
1. Choose **Approve** or **Reject**
2. Estimate the **probability of default** (0% to 100%); this is required

You will first complete 2 practice trials with feedback, then 18 scored trials.

"""

# -----------------------------------------------------------------------------
# Quiz
# -----------------------------------------------------------------------------

QUIZ_QUESTIONS = [
    {
        "id": 1,
        "question": "If a borrower defaults on their loan, it means:",
        "options": {
            "A": "They repaid the loan early",
            "B": "They failed to repay the loan",
            "C": "They requested a lower interest rate",
            "D": "The bank approved a second loan",
        },
        "correct": "B",
    },
    {
        "id": 2,
        "question": "You approve a loan application. The borrower then defaults. How much does this cost?",
        "options": {
            "A": "$1,000",
            "B": "$5,000",
            "C": "Nothing",
            "D": "$10,000",
        },
        "correct": "B",
    },
    {
        "id": 3,
        "question": "You reject a loan application. The borrower would have repaid. How much does this cost?",
        "options": {
            "A": "$5,000",
            "B": "Nothing",
            "C": "$1,000",
            "D": "$2,500",
        },
        "correct": "C",
    },
]

QUIZ_PASS_THRESHOLD = 2                      # must answer at least this many correctly
QUIZ_MAX_ATTEMPTS = 2

QUIZ_INTRO = (
    "Before you begin, please answer these 3 short questions to confirm you understand the task. "
    f"You need to answer at least {QUIZ_PASS_THRESHOLD} correctly to continue."
)

QUIZ_RETRY_INTRO = (
    "Some answers were not quite right. Please review the instructions above and try again. "
    "This is your final attempt."
)

QUIZ_FAILED_WARNING = (
    "Thank you for your attempt. Before continuing, please review the key points below one more time:"
)

QUIZ_KEY_POINTS = """
- A **default** means the borrower failed to repay the loan.
- Approving a loan that defaults costs your bank **$5,000**.
- Rejecting a loan that would have been repaid costs your bank **$1,000**.
- Approving a bad loan is **5 times more costly** than rejecting a good one.
"""

# -----------------------------------------------------------------------------
# Practice / Block intros
# -----------------------------------------------------------------------------

PRACTICE_INTRO = """
### Practice

You will now complete **2 practice trials** to familiarize yourself with the task.
After each practice decision, you will see the correct outcome and how your choice compared
to the cost-minimizing strategy.

These trials do not count toward your final score.
"""

BLOCK_HEADERS = {
    "no_ai": (
        "In this round, you will make decisions **on your own**, without AI assistance."
    ),
    "ai_first": (
        "In this round, you will see the **AI's assessment before** making your decision."
    ),
    "human_first": (
        "In this round, you will **first make your own decision**, then see the AI's "
        "assessment and have a chance to revise."
    ),
}

BLOCK_NUMBER = {"block_1": 1, "block_2": 2, "block_3": 3}

# -----------------------------------------------------------------------------
# Reflection (metacognitive self-report, before trust rating)
# -----------------------------------------------------------------------------

REFLECTION_INTRO = (
    "Before we finish, two quick questions about how you approached the task. "
    "There are no right or wrong answers."
)

RELIANCE_QUESTION = (
    "In the rounds where you saw AI predictions, how often did you change your "
    "mind after seeing the AI's estimate?"
)
RELIANCE_OPTIONS = ["Never", "Rarely", "Sometimes", "Often", "Always"]

SURPRISE_QUESTION = (
    "When the AI's prediction surprised you (was very different from what you "
    "expected), what did you usually do?"
)
SURPRISE_OPTIONS = [
    "Went with the AI anyway",
    "Stuck with my original judgment",
    "It depended on the case",
]

# -----------------------------------------------------------------------------
# Trust / thank you / performance
# -----------------------------------------------------------------------------

TRUST_QUESTION = "Overall, how much did you trust the AI's predictions?"
TRUST_LABELS = {
    1: "1 — Not at all",
    2: "2 — Slightly",
    3: "3 — Moderately",
    4: "4 — Quite a bit",
    5: "5 — Completely",
}

THANK_YOU_TEXT = """
### Thank you for completing the study!

Your responses have been recorded.

If you have questions about this research, contact: **anna_asatryan2@edu.aua.am**
"""

ALREADY_COMPLETED_TEXT = """
### You have already completed this study

Our records show that this browser session has already submitted a completed run of the
experiment. To preserve data quality, each participant may only take part once.

Thank you for your interest.
"""

# Performance-tier messages appended to the score summary.
# The buckets are computed as (total_cost - optimal_cost) in config.utils.performance_tier.
PERFORMANCE_MESSAGES = {
    "excellent": (
        "Excellent work — your losses are very close to the best possible strategy."
    ),
    "good": (
        "Good work — you performed better than most participants would on this task."
    ),
    "fair": (
        "Thanks for your careful effort. This task is difficult; even skilled practitioners rarely achieve the optimal strategy."
    ),
    "low": (
        "Thank you for participating. This task is genuinely hard and the cost structure "
        "punishes approvals of defaulters heavily."
    ),
}

# -----------------------------------------------------------------------------
# Error / connection
# -----------------------------------------------------------------------------

DB_ERROR_MESSAGE = (
    "We couldn't save your response right now. Please wait a moment and click **Retry**. "
    "If the problem persists, please refresh the page — your progress is saved."
)
