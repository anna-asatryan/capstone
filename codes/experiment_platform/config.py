"""
Experiment-wide constants: cost parameters, case data, protocol rotation,
all user-facing text, quiz questions, and display mappings.

Edit this file to change wording, case data, quiz content, or experiment
parameters. No other module should hold user-facing strings.
"""

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
# CASE DATA
# =============================================================================

EXPERIMENTAL_CASES = [
    {
        "case_id": 777203, "case_position": 1, "block": "block_1",
        "loan_amnt": 18000, "term": "60 months", "int_rate": 10.91,
        "log_annual_inc": 10.71444, "dti": 23.49, "revol_util": 43.0,
        "home_ownership": "RENT", "purpose": "debt_consolidation",
        "credit_history_years": 7.92,
        "pred_prob": 0.311574, "y_true": 1,
        "difficulty_tier": "easy", "difficulty_score": 0.307547,
        "correct": 0, "model_optimal": 0,
    },
    {
        "case_id": 49639, "case_position": 2, "block": "block_1",
        "loan_amnt": 11000, "term": "36 months", "int_rate": 5.32,
        "log_annual_inc": 10.59666, "dti": 10.92, "revol_util": 35.9,
        "home_ownership": "MORTGAGE", "purpose": "debt_consolidation",
        "credit_history_years": 27.75,
        "pred_prob": 0.054726, "y_true": 0,
        "difficulty_tier": "easy", "difficulty_score": 0.162701,
        "correct": 1, "model_optimal": 1,
    },
    {
        "case_id": 765600, "case_position": 3, "block": "block_1",
        "loan_amnt": 30225, "term": "60 months", "int_rate": 30.75,
        "log_annual_inc": 11.050906, "dti": 29.2, "revol_util": 92.9,
        "home_ownership": "RENT", "purpose": "debt_consolidation",
        "credit_history_years": 19.25,
        "pred_prob": 0.868101, "y_true": 0,
        "difficulty_tier": "hard", "difficulty_score": 0.78429,
        "correct": 0, "model_optimal": 1,
    },
    {
        "case_id": 37221, "case_position": 4, "block": "block_1",
        "loan_amnt": 18000, "term": "60 months", "int_rate": 28.72,
        "log_annual_inc": 10.085851, "dti": 39.53, "revol_util": 96.4,
        "home_ownership": "OWN", "purpose": "credit_card",
        "credit_history_years": 18.25,
        "pred_prob": 0.94613, "y_true": 1,
        "difficulty_tier": "hard", "difficulty_score": 0.744436,
        "correct": 1, "model_optimal": 1,
    },
    {
        "case_id": 2668, "case_position": 5, "block": "block_1",
        "loan_amnt": 11450, "term": "36 months", "int_rate": 15.02,
        "log_annual_inc": 10.999446, "dti": 16.06, "revol_util": 66.3,
        "home_ownership": "RENT", "purpose": "moving",
        "credit_history_years": 6.17,
        "pred_prob": 0.234348, "y_true": 1,
        "difficulty_tier": "medium", "difficulty_score": 0.377186,
        "correct": 0, "model_optimal": 0,
    },
    {
        "case_id": 161, "case_position": 6, "block": "block_1",
        "loan_amnt": 4000, "term": "36 months", "int_rate": 18.94,
        "log_annual_inc": 12.072547, "dti": 18.78, "revol_util": 59.4,
        "home_ownership": "MORTGAGE", "purpose": "credit_card",
        "credit_history_years": 28.5,
        "pred_prob": 0.168642, "y_true": 0,
        "difficulty_tier": "medium", "difficulty_score": 0.592555,
        "correct": 1, "model_optimal": 0,
    },
    {
        "case_id": 6272, "case_position": 7, "block": "block_2",
        "loan_amnt": 40000, "term": "60 months", "int_rate": 13.56,
        "log_annual_inc": 11.512935, "dti": 6.02, "revol_util": 20.6,
        "home_ownership": "MORTGAGE", "purpose": "small_business",
        "credit_history_years": 12.0,
        "pred_prob": 0.333333, "y_true": 1,
        "difficulty_tier": "easy", "difficulty_score": 0.30891,
        "correct": 0, "model_optimal": 0,
    },
    {
        "case_id": 241937, "case_position": 8, "block": "block_2",
        "loan_amnt": 10000, "term": "36 months", "int_rate": 9.8,
        "log_annual_inc": 11.314487, "dti": 9.56, "revol_util": 84.0,
        "home_ownership": "MORTGAGE", "purpose": "debt_consolidation",
        "credit_history_years": 3.92,
        "pred_prob": 0.074984, "y_true": 0,
        "difficulty_tier": "easy", "difficulty_score": 0.225732,
        "correct": 1, "model_optimal": 1,
    },
    {
        "case_id": 791841, "case_position": 9, "block": "block_2",
        "loan_amnt": 25450, "term": "60 months", "int_rate": 30.84,
        "log_annual_inc": 11.002117, "dti": 28.8, "revol_util": 74.0,
        "home_ownership": "RENT", "purpose": "debt_consolidation",
        "credit_history_years": 7.5,
        "pred_prob": 0.842869, "y_true": 0,
        "difficulty_tier": "hard", "difficulty_score": 0.78429,
        "correct": 0, "model_optimal": 1,
    },
    {
        "case_id": 165503, "case_position": 10, "block": "block_2",
        "loan_amnt": 13200, "term": "60 months", "int_rate": 28.14,
        "log_annual_inc": 10.404293, "dti": 39.53, "revol_util": 54.3,
        "home_ownership": "RENT", "purpose": "debt_consolidation",
        "credit_history_years": 11.92,
        "pred_prob": 0.923224, "y_true": 1,
        "difficulty_tier": "hard", "difficulty_score": 0.744436,
        "correct": 1, "model_optimal": 1,
    },
    {
        "case_id": 776034, "case_position": 11, "block": "block_2",
        "loan_amnt": 8750, "term": "36 months", "int_rate": 12.62,
        "log_annual_inc": 10.308986, "dti": 29.88, "revol_util": 13.4,
        "home_ownership": "RENT", "purpose": "debt_consolidation",
        "credit_history_years": 15.5,
        "pred_prob": 0.267119, "y_true": 1,
        "difficulty_tier": "medium", "difficulty_score": 0.353885,
        "correct": 0, "model_optimal": 0,
    },
    {
        "case_id": 710322, "case_position": 12, "block": "block_2",
        "loan_amnt": 32000, "term": "60 months", "int_rate": 13.99,
        "log_annual_inc": 12.398217, "dti": 15.28, "revol_util": 68.5,
        "home_ownership": "MORTGAGE", "purpose": "credit_card",
        "credit_history_years": 12.5,
        "pred_prob": 0.188803, "y_true": 0,
        "difficulty_tier": "medium", "difficulty_score": 0.343912,
        "correct": 1, "model_optimal": 0,
    },
    {
        "case_id": 29292, "case_position": 13, "block": "block_3",
        "loan_amnt": 19200, "term": "60 months", "int_rate": 15.04,
        "log_annual_inc": 11.396403, "dti": 2.55, "revol_util": 4.8,
        "home_ownership": "RENT", "purpose": "small_business",
        "credit_history_years": 12.67,
        "pred_prob": 0.37037, "y_true": 1,
        "difficulty_tier": "easy", "difficulty_score": 0.328147,
        "correct": 0, "model_optimal": 0,
    },
    {
        "case_id": 727176, "case_position": 14, "block": "block_3",
        "loan_amnt": 12000, "term": "36 months", "int_rate": 7.99,
        "log_annual_inc": 10.819798, "dti": 17.15, "revol_util": 23.9,
        "home_ownership": "OWN", "purpose": "home_improvement",
        "credit_history_years": 37.92,
        "pred_prob": 0.101631, "y_true": 0,
        "difficulty_tier": "easy", "difficulty_score": 0.141881,
        "correct": 1, "model_optimal": 1,
    },
    {
        "case_id": 785690, "case_position": 15, "block": "block_3",
        "loan_amnt": 35000, "term": "60 months", "int_rate": 28.72,
        "log_annual_inc": 10.308986, "dti": 26.48, "revol_util": 48.7,
        "home_ownership": "RENT", "purpose": "credit_card",
        "credit_history_years": 14.0,
        "pred_prob": 0.822149, "y_true": 0,
        "difficulty_tier": "hard", "difficulty_score": 0.744436,
        "correct": 0, "model_optimal": 1,
    },
    {
        "case_id": 274352, "case_position": 16, "block": "block_3",
        "loan_amnt": 14075, "term": "60 months", "int_rate": 30.84,
        "log_annual_inc": 10.59666, "dti": 27.36, "revol_util": 49.5,
        "home_ownership": "RENT", "purpose": "debt_consolidation",
        "credit_history_years": 11.08,
        "pred_prob": 0.901361, "y_true": 1,
        "difficulty_tier": "hard", "difficulty_score": 0.744436,
        "correct": 1, "model_optimal": 1,
    },
    {
        "case_id": 208784, "case_position": 17, "block": "block_3",
        "loan_amnt": 8725, "term": "36 months", "int_rate": 18.99,
        "log_annual_inc": 10.16589, "dti": 5.22, "revol_util": 35.5,
        "home_ownership": "OWN", "purpose": "debt_consolidation",
        "credit_history_years": 6.5,
        "pred_prob": 0.289308, "y_true": 1,
        "difficulty_tier": "medium", "difficulty_score": 0.524324,
        "correct": 0, "model_optimal": 0,
    },
    {
        "case_id": 33, "case_position": 18, "block": "block_3",
        "loan_amnt": 2500, "term": "36 months", "int_rate": 18.94,
        "log_annual_inc": 11.461643, "dti": 17.34, "revol_util": 31.0,
        "home_ownership": "MORTGAGE", "purpose": "debt_consolidation",
        "credit_history_years": 16.0,
        "pred_prob": 0.210035, "y_true": 0,
        "difficulty_tier": "medium", "difficulty_score": 0.584377,
        "correct": 1, "model_optimal": 0,
    },
]

PRACTICE_CASES = [
    {
        "case_id": 731479, "case_position": -2, "block": "practice",
        "loan_amnt": 5000, "term": "36 months", "int_rate": 8.24,
        "log_annual_inc": 11.561725, "dti": 1.05, "revol_util": 5.2,
        "home_ownership": "RENT", "purpose": "moving",
        "credit_history_years": 24.75,
        "pred_prob": 0.058615, "y_true": 0,
        "difficulty_tier": "easy", "difficulty_score": 0.089268,
        "correct": 1, "model_optimal": 1,
    },
    {
        "case_id": 252416, "case_position": -1, "block": "practice",
        "loan_amnt": 22000, "term": "60 months", "int_rate": 19.89,
        "log_annual_inc": 10.691968, "dti": 31.15, "revol_util": 51.6,
        "home_ownership": "RENT", "purpose": "debt_consolidation",
        "credit_history_years": 15.5,
        "pred_prob": 0.578106, "y_true": 1,
        "difficulty_tier": "hard", "difficulty_score": 0.781741,
        "correct": 1, "model_optimal": 1,
    },
]

# =============================================================================
# PROTOCOL ROTATION (Latin Square)
# =============================================================================

PROTOCOL_ROTATION = {
    "group_1": {"block_1": "no_ai",        "block_2": "human_first", "block_3": "ai_first"},
    "group_2": {"block_1": "human_first",  "block_2": "ai_first",    "block_3": "no_ai"},
    "group_3": {"block_1": "ai_first",     "block_2": "no_ai",       "block_3": "human_first"},
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
