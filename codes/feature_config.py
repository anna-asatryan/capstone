FEATURES = [
    'loan_amnt',
    'term',
    'int_rate',
    'dti',
    'revol_util',
    'home_ownership',
    'purpose',
    'log_annual_inc',
    'credit_history_years'
]

TARGET = 'target'


# types
NUM_COLS = [
    'loan_amnt',
    'int_rate',
    'log_annual_inc',
    'dti',
    'credit_history_years',
    'revol_util'
    # 'dti_income_interaction'
]

CAT_COLS = [
    'home_ownership',
    'purpose',
    'term'
]